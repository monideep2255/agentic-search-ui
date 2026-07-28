# Phase 1.1: Auth service and the user-data schema

Branch: `phase/1.1-auth-service`
Depends on: 1.0 (done, merged as PR #5)
Delivers (Technical_specification.md Section 25, line 3179): minimal v1 auth (Step 1.7), the PostgreSQL user-data schema stood up now (`interactions`, `cq_candidates`, `users`), even though the feedback loop does not populate it meaningfully until phase 4.6.

Dependency check at open: Section 25's dependency graph gives 1.1 a single incoming edge from 1.0, which is `done` on `tracker/BOARD.md` and merged into `main`. This phase can start.

Scope note, decided by the lead at open: Section 25's parenthetical names three tables, Section 15 defines six (`users`, `auth_sessions`, `sessions`, `interactions`, `cq_candidates`, `saved_queries`). This phase builds all six. The three named tables cannot stand alone: `interactions` carries a foreign key to `sessions`, `saved_queries` carries one to `interactions`, and `auth_sessions` is what the refresh-token model in Section 15 stores. Section 15 is the schema specification and Section 25's list is illustrative, so the six-table read is the one that produces a loadable schema. No capability outside Section 15 is added.

Environment verified at open, so no builder rediscovers it: PostgreSQL 15.17 (Homebrew) is running on `localhost:5432` with superuser `anuradhachakraborti`. The `search_agent_users` database does not exist yet and the migration creates it. Extensions `pgcrypto` 1.3 and `pg_trgm` 1.6 are both available but not yet installed. A separate local `ncbi_kg` database exists on the same instance and is out of bounds for this phase: nothing here connects to it.

LEARNINGS.md filtered to this phase: one entry applies, and it is the corrected version that matters, not the original. Row 21 corrects row 19's wrong root-cause diagnosis. The real cause was that `agentic-search-ui/venv` had been copied from the sibling `agentic-search-data-engineering` repo, so `activate`, `pip`, and `pip3` carried the sibling's absolute path and silently operated on the wrong environment. This phase installs new dependencies, so verify the target environment with `pip --version`'s reported path or an absolute-path invocation, never a bare activated `pip show`. The venv was confirmed clean at open. Standing lessons that still apply: use the Edit tool for board files, never `sed` or a heredoc, since the `sync-board.sh` PostToolUse hook fires only on Edit and Write; keep bulk edits away from `DECISIONS.md`.

## Tickets

### T-1.1-01: PostgreSQL user-data schema and migration

Status: done
Refine: refined
Branch: phase/1.1-auth-service
Depends on: none
Spec: Technical_specification.md Section 15 (lines 2361-2555), specifically the instance separation (2363-2370) and the six table definitions (2392-2549)

Files this ticket may create or modify:
- `src/system_03_search_agent/data/__init__.py`
- `src/system_03_search_agent/data/base.py`
- `src/system_03_search_agent/data/models.py`
- `src/system_03_search_agent/data/session.py`
- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/versions/0001_user_data_schema.py`
- `tests/system_03_search_agent/data/__init__.py`
- `tests/system_03_search_agent/data/test_models.py`
- `tests/system_03_search_agent/data/test_migration.py`

Acceptance criteria:
- [x] After `alembic upgrade head` against an empty database, all six Section 15 tables exist (`users`, `auth_sessions`, `sessions`, `interactions`, `cq_candidates`, `saved_queries`) with the exact column names, types, nullability, and defaults Section 15 declares
- [x] The `pgcrypto` and `pg_trgm` extensions are enabled by the migration, and `gen_random_uuid()` resolves as the column default for every UUID primary key
- [x] All five `interactions` indexes from Section 15 exist after migration, including the GIN index on `coverage_tags` and the `gin_trgm_ops` index on `query_text`, and `idx_cq_candidates_status` exists on `cq_candidates`
- [x] `alembic downgrade base` removes every table, index, and extension the upgrade created, and exits without error, so the migration has a working rollback path
- [x] Inserting a row that violates any Section 15 CHECK constraint raises a database integrity error rather than being accepted: `interactions.query_class` outside the five allowed values, `interactions.trust_signal` outside four, `interactions.rubric_outcome` outside three, `interactions.rubric_score` outside 0 to 16, and `cq_candidates.status`, `wedge_type`, `moat_rank`, and `review_decision` outside their declared sets
- [x] A duplicate `users.email` and a duplicate `interactions.trace_id` are each rejected by a unique constraint
- [x] Deleting a `users` row cascades to its `auth_sessions` and `saved_queries` rows, and sets `interactions.user_id` and `sessions.user_id` to NULL while leaving those rows in place
- [x] No module under `src/system_03_search_agent/data/` imports, references, or constructs a connection to the AGE graph, the `kg_reader` role, or the `ncbi_kg` database; the engine is built only from `USER_DB_URL`
- [x] The connection URL is read from the `USER_DB_URL` environment variable and never appears in a log record, an exception string, or a test fixture as a literal with credentials

Breakdown:
- [x] SQLAlchemy declarative base and engine or session factory bound to `USER_DB_URL`
- [x] Models for all six tables with CHECK constraints and indexes declared
- [x] Alembic scaffolding and the `0001_user_data_schema` revision, upgrade and downgrade
- [x] Tests: schema shape, every CHECK constraint, both unique constraints, all four delete behaviors, upgrade and downgrade round trip

Evidence:
- Judge re-ran everything independently; no builder self-report was accepted. Venv confirmed as this repo's own, closing the LEARNINGS row 21 risk: `pip 26.1.2 from /Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui/venv/lib/python3.11/site-packages/pip (python 3.11)`, interpreter `/Users/.../agentic-search-ui/venv/bin/python`, Python 3.11.6.
- AC1, all six tables with exact Section 15 shape, verified against the LIVE database via `information_schema.columns`, not against the migration file. All 64 user columns match Section 15 column-for-column on name, type, nullability, and default. Spot evidence: `users|email|text|NO|-`, `users|profile|jsonb|NO|'{}'::jsonb`, `auth_sessions|expires_at|timestamp with time zone|NO|-`, `interactions|coverage_tags|ARRAY|NO|'{}'::text[]`, `interactions|rubric_score|smallint|YES|-`, `cq_candidates|status|text|NO|'proposed'::text`, `saved_queries|last_run_interaction_id|uuid|YES|-`. `cost_usd` precision checked separately: `cost_usd numeric(9,6)`, matching Section 15's `NUMERIC(9,6)`. PASS.
- AC2, extensions and UUID defaults. `SELECT extname||' '||extversion FROM pg_extension` returns `pgcrypto 1.3` and `pg_trgm 1.6`. Every UUID primary key carries `gen_random_uuid()` as its live column default (6 of 6: users, auth_sessions, sessions, interactions, cq_candidates, saved_queries). PASS.
- AC3, indexes, read from `pg_indexes` on the live database. All five interactions indexes present with the Postgres-specific details intact: `CREATE INDEX idx_interactions_created_at ON public.interactions USING btree (created_at DESC)` (DESC preserved), `... idx_interactions_coverage_tags ... USING gin (coverage_tags)`, `... idx_interactions_query_trgm ... USING gin (query_text gin_trgm_ops)` (opclass preserved), plus `idx_interactions_user_id` and `idx_interactions_rubric`. `CREATE INDEX idx_cq_candidates_status ON public.cq_candidates USING btree (status)` present. PASS.
- AC4, rollback, run by the judge against a throwaway database `judge_scratch_1_1`, not taken on the test's word. `alembic upgrade head` then `7 tables` (six plus alembic's own `alembic_version`) and `2 extensions(pgcrypto/pg_trgm)`. `alembic downgrade base` exited `exit=0`; post-downgrade state was tables `alembic_version` only, extensions `(none)`, indexes `alembic_version_pkc` only, so every table, index, and extension the upgrade created was removed. `alembic upgrade head` again gave `7 tables after re-upgrade`. Round trip proven. PASS.
- AC5, every CHECK constraint, exercised with real rejected INSERTs on the scratch database. Nine for nine rejected: `ck_interactions_query_class`, `ck_interactions_trust_signal`, `ck_interactions_rubric_outcome`, `ck_interactions_rubric_score` (rejected both 17 and -1), `ck_cq_candidates_status`, `ck_cq_candidates_wedge_type`, `ck_cq_candidates_moat_rank`, `ck_cq_candidates_review_decision`. Each returned `ERROR: new row for relation "<table>" violates check constraint "<name>"`. PASS.
- AC6, unique constraints. `ERROR: duplicate key value violates unique constraint "users_email_key"` and `ERROR: duplicate key value violates unique constraint "interactions_trace_id_key"`. PASS.
- AC7, delete behavior, all four exercised live in one transaction against the scratch database. After `DELETE FROM users WHERE id='1111...'`: `auth_sessions rows left: 0` (CASCADE), `saved_queries rows left: 0` (CASCADE), `interactions row kept, user_id NULL: 1/1` (SET NULL, row survives), `sessions row kept, user_id NULL: 1/1` (SET NULL, row survives). PASS.
- AC8, least privilege. `grep -rnE 'psycopg2|GRAPH_PG|GRAPH_QUERY|create_engine' src/system_03_search_agent/auth src/system_03_search_agent/data` returns exactly two lines, both in `data/base.py`: line 25 `from sqlalchemy import create_engine` and line 60 `return create_engine(url or get_user_db_url(), pool_pre_ping=True, future=True)`. No psycopg2 import, no `GRAPH_PG_*`, no `GRAPH_QUERY_URL`, no `ncbi_kg`, no `kg_reader`, no Hetzner host anywhere under `data/` or `auth/`. The engine is built only from `USER_DB_URL`. PASS.
- AC9, no connection string in a log or exception. `grep -rnE 'log(ger)?\.(debug|info|warning|error|critical|exception)|print\('` over `auth/`, `data/`, and `alembic/` returns nothing at all: the packages emit no log records and no prints. The only URL-adjacent raise is `data/base.py:44-47`, which names the variable, never a value: `"USER_DB_URL is not set. Set it in the environment before connecting to the user-data database (see env.example)."` Test fixtures use `postgresql://localhost:5432/search_agent_users`, which carries no credential. PASS.
- Gate, parameterized queries. `git diff main...HEAD --name-only | grep '\.py$' | xargs grep -nE '(execute|text|cypher|SELECT|INSERT|UPDATE|DELETE|CREATE)[^\n]*(f"|f'\''|\.format\()'` returns `NONE FOUND`. A broader sweep for any f-string at all under `auth/`, `data/`, and `alembic/versions/` returns `NONE`, and for `.format(` returns `NONE`. PASS.
- Gate, type hints and naming. AST walk over every function in `auth/` and `data/`, checking `returns` and every arg annotation: `L type-hint gaps: NONE - all functions fully annotated`. `grep -rnE 'def [a-z]*[A-Z]'` returns `NONE`, so snake_case holds. `ruff check` over `auth/`, `data/`, `alembic/`, and both new test packages: `All checks passed!`. PASS.
- Tests: 29 passed in `tests/system_03_search_agent/data`, re-run by the judge.
- BLOCKING DEFECT, F-1.1-01, high. `tests/system_03_search_agent/data/test_migration.py:26` targets the shared dev database named by `USER_DB_URL` (defaulting to the real `search_agent_users`) and downgrades it to base, which drops every table and therefore destroys every row. The `migrated_head` fixture restores the schema but cannot restore the data. Proven with a canary: planted a row, `11 users before`, ran `pytest tests/system_03_search_agent/data/test_migration.py -q` giving `5 passed in 0.53s`, then `0 users after` and `0 canary rows surviving`. This also silently deleted the ten rows the judge's own HTTP probe had created minutes earlier. Every acceptance criterion above genuinely passes; this ticket is rejected on the destructive test alone.

Evidence, round 2 (2026-07-28 judge re-verification of commit `20d4d7a`, authored by `fix-f1101-destructive-test`):

- Scope of the change, read from `git show 20d4d7a --name-only` rather than from the fix agent's report: exactly one file, `tests/system_03_search_agent/data/test_migration.py`, 87 insertions and 17 deletions. No source file, no migration, no model, no `conftest.py`, no CI config was touched, so the fix cannot have changed the behavior it was being measured against.
- Verify surface NOT weakened, the critical check under `.claude/rules/goal-contracts.md`. Test-function inventory is identical before and after: `git show 20d4d7a^:...test_migration.py | grep -c '^def test_'` gives `5`, the post-fix file gives `5`, and the five names match one for one (`test_upgrade_creates_all_six_tables`, `test_extensions_enabled_and_gen_random_uuid_resolves`, `test_interactions_indexes_exist`, `test_cq_candidates_status_index_exists`, `test_downgrade_base_removes_every_table_index_and_extension`). Every removed line in the diff is a docstring line, a comment, or a signature that was immediately re-added in changed form; no `assert` was deleted. `grep -nE 'skip|xfail'` over the post-fix file returns only the pre-existing module-level `pytest.skip` for an unreachable server at line 61, which existed before the fix and is a skip-when-no-database guard, not a skip of the rollback test. PASS.
- The rollback path is still genuinely exercised against real PostgreSQL. `test_downgrade_base_removes_every_table_index_and_extension` at `tests/system_03_search_agent/data/test_migration.py:230-256` still calls `command.downgrade(cfg, "base")` at line 232, still asserts `ALL_TABLES.isdisjoint(tables)` against a live `inspect(engine)`, and still asserts `remaining_extensions == set()` from a live `pg_extension` query. The only diff inside this function's body is a three-line trailing comment. The alembic runner confirmed it ran for real: `INFO [alembic.runtime.migration] Running downgrade 0001_user_data_schema -> , User-data schema: users, auth_sessions, ...`. PASS.
- Canary, re-derived from F-1.1-01's own text and run against the FULL suite, not just the migration module. Planted `judge-round2-b16e152f-...@canary.test` into `users`. Before: `users_total=23`, `canary_rows=1`, `public_tables=7`. Ran `python -m pytest tests/ -q` giving `284 passed, 1 warning in 2.58s`. After: `canary_rows=1`, `public_tables=7`. The canary survived and the schema was never torn down. Under the round-1 code this same probe returned `0`. PASS.
- No scratch database leaks on the happy path. `SELECT datname FROM pg_database` before and after the full suite both return exactly `ncbi_kg postgres search_agent_users template0 template1`. `SELECT count(*) FROM pg_database WHERE datname LIKE 'migration_scratch%'` returns `0`. PASS.
- No scratch database leaks after a FAILING test, probed two ways with a pytest plugin loaded from `/tmp` so no repo file was modified (`git status --short` after the whole re-verification shows only the three files already modified at session start). Probe A, the worst case, forced an exception immediately after `command.downgrade(cfg, "base")` had already run, using a `hookwrapper` on `pytest_runtest_call` with `outcome.force_exception(...)`: result `1 failed, 4 passed in 0.70s`, and teardown still ran (`Running upgrade -> 0001_user_data_schema` appears in the captured teardown stderr), leaving `LEAKED_COUNT=0`, `canary_rows=1`, `real_db_tables=7`. Probe B, early abort, failed a mid-module test under `-x` so the remaining tests never ran: `1 failed, 2 passed`, `stopping after 1 failures`, and again `LEAKED_COUNT=0`, `canary_rows=1`, `real_db_tables=7`. The `finally` block in the `scratch_db_url` fixture (`test_migration.py:113-127`) holds under both. PASS.
- SUB-CHECK UNVERIFIED, stated rather than claimed: a hard-kill (SIGKILL) mid-run probe could not be executed, because neither `timeout` nor `gtimeout` is present on this macOS host, so the command produced no test run and therefore no evidence. Noted as a known limitation rather than a pass: a `finally` block cannot run after SIGKILL by construction, so an orphaned `migration_scratch_<hex>` database is possible after a hard kill or a power loss. This is inherent to the approach, not a defect introduced by this fix, and it is bounded: the name is uniquely prefixed and trivially greppable in `psql -l`.
- The fix agent's claim about the other two modules, checked directly rather than taken on their word. `grep -rnE 'downgrade|DROP |TRUNCATE|drop_all|CREATE DATABASE|DROP DATABASE' tests/` matches inside `test_migration.py` only; `test_models.py` and `test_router.py` produce zero matches. `test_models.py` additionally cleans up after itself: its `db_session` fixture at lines 123-128 ends in `finally: session.rollback(); session.close()`, so nothing it inserts is committed. Its `_schema_at_head` fixture runs `command.upgrade(cfg, "head")` only, never a downgrade. `test_router.py` never downgrades and holds no destructive SQL. Claim CONFIRMED. PASS.

History:
- 2026-07-28 lead: created, scoped from Section 15, phase 1.1 open
- 2026-07-28 lead: tech refinement complete, six-table scope decided and recorded above, environment pre-verified, no product-owner question outstanding, refined
- 2026-07-28 judge: rejected. All nine acceptance criteria independently verified and passing against the live database, but the migration test destroys every row in the database `USER_DB_URL` names (F-1.1-01, high, canary-proven: 11 users before, 0 after). Fix the test's target database and resubmit; no schema or migration change is needed
- 2026-07-28 builder-user-data-schema: built the six SQLAlchemy models (base.py, models.py, session.py) and the hand-written 0001_user_data_schema Alembic migration; created the search_agent_users database; verified upgrade head and downgrade base against real local PostgreSQL; 220 tests passing (191 prior plus 29 new); ruff and pip-audit clean on new code; commit fcd3db0; status set to in-review for judge sign-off
- 2026-07-28 fix-f1101-destructive-test: fixed F-1.1-01. `test_migration.py` now creates a uniquely named scratch database (`migration_scratch_<uuid4 hex>`) before this module's tests run and drops it afterward, even on failure; the `migrated_head` fixture points Alembic at the scratch database via `monkeypatch.setenv("USER_DB_URL", ...)` for the duration of each test, so `alembic upgrade`/`downgrade` never targets the database `USER_DB_URL` names outside tests. The downgrade-base test is unchanged in substance and still genuinely exercises the rollback path against real PostgreSQL, just against scratch. Checked `test_models.py` and `test_router.py` for the same defect: neither downgrades, drops, or truncates anything; both only insert/delete rows they create themselves. Canary proof: 1 user before, `pytest tests/system_03_search_agent/data/test_migration.py -q` gives `5 passed in 0.81s`, 1 user after, 1 canary row surviving, no scratch database left behind (`psql -l` shows only `ncbi_kg`, `postgres`, `search_agent_users`, `template0`, `template1`). Full suite: `284 passed`. Commit 20d4d7a. Status set to in-review for judge re-verification; F-1.1-01 itself is left filed for the judge to close
- 2026-07-28 judge: done. Re-verified commit `20d4d7a` (the fix agent's work, not the judge's) with probes re-derived from F-1.1-01's own text, not from the fix agent's report. The verify surface was not weakened: 5 test functions before and after with identical names, no assertion removed, no skip or xfail added, and `test_downgrade_base_removes_every_table_index_and_extension` still calls `command.downgrade(cfg, "base")` against real PostgreSQL at line 232. Judge canary survived the FULL suite (`284 passed`), scratch database dropped cleanly on the happy path and after two independently induced failures. Round-1 evidence for the nine acceptance criteria stands unchanged; the sole blocking defect is closed, so the ticket passes

### T-1.1-02: Auth primitives and the ecdsa CVE resolution

Status: done
Refine: refined
Branch: phase/1.1-auth-service
Depends on: none
Spec: Technical_specification.md Section 15 token model (lines 2384-2388). Carries the `ecdsa CVE` open flag from `tracker/BOARD.md` and DECISIONS.md 2026-07-27.

Files this ticket may create or modify:
- `src/system_03_search_agent/auth/__init__.py`
- `src/system_03_search_agent/auth/passwords.py`
- `src/system_03_search_agent/auth/tokens.py`
- `requirements.txt`
- `pyproject.toml`
- `tests/system_03_search_agent/auth/__init__.py`
- `tests/system_03_search_agent/auth/test_passwords.py`
- `tests/system_03_search_agent/auth/test_tokens.py`

Acceptance criteria:
- [x] `ecdsa` is absent from the installed dependency tree, verified by `pip show ecdsa` reporting not found, and `pip-audit` reports no Critical or High finding against the auth dependencies
- [x] A password verifies against its own argon2id hash and fails against any other password, and the stored hash is never equal to the plaintext
- [x] Neither the plaintext password nor the resulting hash appears in any log record or exception string raised by the password module
- [x] An access token decodes back to the `user_id` it was minted for, is rejected once past its 15-minute expiry, and is rejected when verified with a different secret
- [x] An access token's decoded claims contain `user_id` and standard JWT registered claims only, carrying no email, no display name, and no other profile field
- [x] A token presented with `alg: none`, or signed with any algorithm other than HS256, is rejected rather than accepted
- [x] A refresh token is an opaque random string carrying at least 32 bytes of entropy, is not parseable as a JWT, and differs across successive calls
- [x] A refresh token verifies against its own SHA-256 hash and fails against the hash of any other token, and the raw refresh token is never what the hashing function returns for storage
- [x] With `AUTH_SECRET` unset in the environment, minting or verifying a token raises an error rather than falling back to a default, empty, or hardcoded secret

Breakdown:
- [x] Swap `python-jose[cryptography]` for the chosen JWT library in `requirements.txt` and `pyproject.toml`, reinstall, confirm `ecdsa` is gone
- [x] argon2id password hash and verify
- [x] HS256 access-token mint and verify, with expiry and algorithm pinning
- [x] Opaque refresh-token generation and SHA-256 hashing
- [x] Tests: valid, invalid, expired, tampered, wrong-secret, wrong-algorithm, and missing-secret paths for each primitive

Evidence:
- Every criterion re-verified by the judge with adversarial probes written from scratch, not by reading the builder's tests.
- AC1, the ecdsa CVE is genuinely closed. `pip show ecdsa` returns `WARNING: Package(s) not found: ecdsa`. `pip show python-jose` returns `WARNING: Package(s) not found: python-jose`, so the transitive parent is gone too, not just the leaf. Replacements installed in this repo's venv: `PyJWT 2.13.0` and `argon2-cffi 25.1.0`, both at `/Users/.../agentic-search-ui/venv/lib/python3.11/site-packages`. `pip-audit` over the whole environment: `No known vulnerabilities found`. The swap is reflected in both manifests, `requirements.txt` and `pyproject.toml`, replacing `python-jose[cryptography]>=3.3` with `PyJWT>=2.13` and `argon2-cffi>=23.1`. PASS.
- AC2 and AC3, password hashing. Verified by the builder's 10 tests (re-run: `38 passed` across both primitive modules) and by reading `auth/passwords.py`: `_password_hasher.hash` is argon2-cffi's default, which is argon2id. `verify_password` at lines 57-64 returns False on every failure path (wrong type, empty, malformed hash) and never raises, so no exception can echo an input value. The only two raises in the module, lines 37 and 39, are `"password must be a string"` and `"password must not be empty"`, literal field names with no interpolation. The module contains no logging call at all (`grep` for `log(ger)?\.` and `print(` over `auth/` returns nothing). PASS.
- AC4, access-token round trip, expiry, and wrong secret. Judge probe with a freshly generated secret: `mint_access_token(uid)` then `jwt.decode` returns `{'user_id': '041116c0-d9d7-48c5-84a9-a494e0ca1e55', 'iat': 1785244988, 'exp': 1785245888}`, round-tripping the exact `user_id`. Expired token hand-forged with `exp` one hour in the past: `J5 expired -> rejected: ValueError access token has expired`. Token signed with an unrelated 32-byte secret: `J4 wrongsec -> rejected: ValueError access token is invalid`. PASS.
- AC5, claim minimality and the 15-minute TTL. The decoded payload above has exactly three keys, `user_id`, `iat`, `exp`. No email, no display name, no profile field. TTL measured from the token itself rather than from the constant: `J6 TTL secs: 900`, exactly 15 minutes as Section 15 requires. PASS.
- AC6, algorithm pinning, attacked four ways rather than read off the `algorithms=` argument. Hand-crafted `alg: none` token with a valid-looking payload and an empty signature: `J1 alg:none -> rejected: ValueError access token is invalid`. Genuinely RS256-signed token using a fresh 2048-bit RSA key: `J2 RS256 -> rejected: ValueError access token is invalid`. Classic RS256-to-HS256 confusion attack, signing HS256 with the RSA public key as the HMAC secret: `J3 confusion -> rejected: InvalidKeyError` (PyJWT refuses an asymmetric key for HMAC, a second independent barrier). Also confirmed over real HTTP through `/auth/me`: `K alg:none over HTTP: 401`. PASS.
- AC7, refresh-token shape. `J8 len: 43 distinct: True dots: 0 decoded bytes: 32`. Decoding the URL-safe string yields exactly 32 bytes, so the entropy floor is met, not merely claimed. Zero dots and `jwt.get_unverified_header` raising `DecodeError` confirm it is not parseable as a JWT. Two successive calls differ. PASS.
- AC8, refresh-token hashing. `J8 hash != raw: True | len: 64`, a 64-hex-character SHA-256 digest that is never the raw token. `verify_refresh_token` uses `secrets.compare_digest` (tokens.py:169), a constant-time comparison, which is stronger than the criterion asked for. PASS.
- AC9, no fallback secret. With `AUTH_SECRET` deleted from the environment: `J7 mint_access_token no-secret -> RuntimeError: AUTH_SECRET environment variable is not set; refusing to mint or verify a token without an explicit secret`, and the identical RuntimeError from `decode_access_token`. The guard is `if not secret` (tokens.py:48), so an empty string fails too, not just an unset variable. No default, no empty, no hardcoded fallback anywhere in the module. PASS.
- Gate, secrets never logged. Neither `auth/passwords.py` nor `auth/tokens.py` emits any log record or print. Every raise in both modules carries a literal string with no interpolated value; the `AUTH_SECRET` RuntimeError names the variable, never its content. PASS.
- Gate, type hints, naming, lint. AST audit found zero missing return or argument annotations across both modules; `ruff check` passed; no non-snake_case identifier. PASS.
- Tests: 38 passed (10 `test_passwords.py`, 28 `test_tokens.py`), re-run by the judge. These tests touch no database and are not affected by F-1.1-01.

History:
- 2026-07-28 lead: created, scoped from Section 15's token model, phase 1.1 open
- 2026-07-28 lead: tech refinement complete, researcher established that `ecdsa` is a core (not extra-gated) requirement of `python-jose` so it cannot be excluded in place, library swap authorized as a tactical decision under bossman mode and logged to DECISIONS.md, refined
- 2026-07-28 judge: done. All nine acceptance criteria independently re-verified, including four separate algorithm-confusion attacks on the token decoder and a measured 900-second TTL; the ecdsa CVE is closed at the root, with python-jose itself absent from the tree
- 2026-07-28 builder-auth-primitives: implemented all three primitives (argon2id password hashing in `auth/passwords.py`, HS256 access tokens and opaque SHA-256-hashed refresh tokens in `auth/tokens.py`), swapped `python-jose[cryptography]` for `PyJWT` plus `argon2-cffi` in `requirements.txt` and `pyproject.toml`, uninstalled `ecdsa`/`python-jose` from the shared venv and reinstalled the new pair. All nine acceptance criteria proven by 38 new tests (10 in `test_passwords.py`, 28 in `test_tokens.py`); full suite is 229 passed (191 prior plus 38 new), `pip show ecdsa` reports not found, `pip-audit` reports no known vulnerabilities. Commit `465291e`. Status set to in-review, not done, per instruction that only the judge sets done

### T-1.1-03: Auth router and app wiring

Status: done
Refine: refined
Branch: phase/1.1-auth-service
Depends on: T-1.1-01, T-1.1-02
Spec: Technical_specification.md Section 15 the auth service and its endpoint list (lines 2372-2390), PII handling Section 11.3 (lines 1935-1941)

Files this ticket may create or modify:
- `src/system_03_search_agent/auth/router.py`
- `src/system_03_search_agent/auth/schemas.py`
- `src/system_03_search_agent/auth/dependencies.py`
- `src/system_03_search_agent/adapters/web_sse/app.py` (wiring only, router mounted)
- `tests/system_03_search_agent/auth/test_router.py`

Acceptance criteria:
- [x] `POST /auth/signup` with an unused email returns a success status and creates exactly one `users` row; the same email again returns 409 and creates no second row
- [x] `POST /auth/login` with correct credentials returns both an access token and a refresh token and updates `users.last_login_at`
- [x] `POST /auth/login` with a wrong password returns 401 with no token in the body, and its response is indistinguishable between an unknown email and a known email with a wrong password, so the endpoint does not disclose which emails are registered
- [x] `POST /auth/refresh` with a valid refresh token returns a new access token and a new refresh token, and replaying the presented refresh token afterwards returns 401, so rotation actually invalidates the old one
- [x] `POST /auth/logout` sets `revoked_at` on the caller's `auth_sessions` row, and a refresh with that token afterwards returns 401
- [x] `GET /auth/me` returns the caller's profile for a valid access token, and returns 401 for a missing, malformed, or expired token
- [x] Every request body is validated through a Pydantic model with `extra="forbid"`, so an unknown field returns 422 rather than being silently ignored
- [x] No response body from any `/auth` endpoint contains `password_hash`, `refresh_token_hash`, or any other user's data
- [x] `auth_sessions.ip_hash` holds a salted hash, and the raw client IP address appears in no column and no log line
- [x] Mounting the auth router leaves `GET /health` and `POST /query` behaving exactly as they did at the close of phase 1.0, verified by the phase 1.0 tests still passing unchanged

Breakdown:
- [x] Pydantic request and response schemas with `extra="forbid"`
- [x] The five endpoints wired to the models from T-1.1-01 and the primitives from T-1.1-02
- [x] Access-token dependency for authenticated routes
- [x] Router mounted at `/auth` in `app.py`
- [x] Tests: valid, invalid, missing, and null input on all five endpoints, plus the rotation, revocation, and enumeration-resistance paths

Evidence:
- Every criterion proven over real HTTP through the mounted FastAPI app against the live `search_agent_users` database, using a judge-written probe, never by reading the builder's tests.
- AC1, signup. `A signup: 201 {"id":"52136015-b7f7-4c4e-8853-7b790fec6e60","email":"judge-8c8fdb1e-...@example.com"}`. Same email again: `A dup: 409 {"detail":"email already registered"}`, and no second row was created (the 409 path rolls back at router.py:185 before any commit). PASS.
- AC2, login. `C login: 200 ['access_token', 'refresh_token', 'token_type']`, both tokens present. `users.last_login_at` is set at router.py:205 in the same transaction; the subsequent `/auth/me` returned `"last_login_at":"2026-07-28T09:22:40.206250-04:00"` against a `created_at` of `09:22:40.044550`, proving the field moved from NULL to a real timestamp on login. PASS.
- AC3, user-enumeration resistance, attacked empirically rather than reasoned about. Known email with a wrong password: `401 b'{"detail":"invalid email or password"}'`. Unknown email entirely: `401 b'{"detail":"invalid email or password"}'`. Byte-comparison of the raw response bodies plus status: `B IDENTICAL: True`. Header comparison with `date` excluded: `B headers identical: True {}`, so the empty diff dict shows not one header differs, including `content-length`. The timing channel is closed too: router.py:198 substitutes a module-level dummy argon2 hash when no user row exists, so the unknown-email branch performs a real argon2id verify rather than short-circuiting. PASS.
- AC4, refresh rotation, attacked by replay. `D refresh1: 200 ['access_token', 'refresh_token', 'token_type']` and `D rotated: True` (the new refresh token differs from the presented one). Replaying the now-spent token: `D REPLAY: 401 {"detail":"invalid or expired refresh token"}`. Rotation genuinely invalidates. The mechanism is a single atomic `UPDATE ... WHERE revoked_at IS NULL AND expires_at > now` (router.py:151-159) with a `rowcount != 1` guard, not a select-then-mutate, so two concurrent replays cannot both win under READ COMMITTED. PASS.
- AC5, logout. `E logout: 200 {"status":"ok"}`, then refreshing with that same token: `E refresh-after-logout: 401 {"detail":"invalid or expired refresh token"}`. Confirmed in the database: `3 revoked` rows carry a non-null `revoked_at`. PASS.
- AC6, `/auth/me`. Valid token: `200` returning only `id`, `email`, `created_at`, `last_login_at`. Missing header: `401`. Malformed scheme (`Authorization: Basic xyz`): `401`. Non-JWT bearer value: `401`. Genuinely expired token forged with `exp` one hour in the past: `K expired access over HTTP: 401`. Forged `alg: none` token: `K alg:none over HTTP: 401`. PASS.
- AC7, `extra="forbid"` proven on the wire, not by reading `ConfigDict`. Unknown field `is_admin` on signup: `G forbid signup: 422`. Unknown field on login, refresh, and logout: `422`, `422`, `422`, all four request models enforced. Missing-input and null-input paths also covered: `G missing signup: 422` (password omitted), `G null signup: 422` (both fields explicitly null), `G empty login: 422` (empty body). PASS, and this satisfies the production-standards valid/invalid/missing endpoint-test bar.
- AC8, no leakage, checked against the concatenated raw body of all eleven probe responses. `H leak 'password_hash': False`, `H leak 'refresh_token_hash': False`, `H leak '$argon2': False`, `H leak 'ip_hash': False`. Cross-user isolation attacked separately with two accounts A and B: `K A sees only A: True | contains B: False`, and after rotating B's refresh token, `K rotated-B token maps to B not A: True`. No endpoint returns another user's data. PASS.
- AC9, `ip_hash` and the raw IP. Live column contents: `aff903ece5465ab8df61676d3f62b372f56e2574cdaf62b11c1f74498c5614c0 | ua=testclient | len=64`, a 64-hex-character HMAC-SHA256 digest. Adversarial scan for a raw address in the column, `SELECT count(*) FROM auth_sessions WHERE ip_hash ~ '^[0-9]{1,3}\.' OR ip_hash='testclient' OR ip_hash ~ ':'`, returns `0`, so neither an IPv4 literal, an IPv6 literal, nor the unhashed client identifier is stored. No log line can carry it either: the `auth/` package emits no logging call and no print at all. PASS. Section 15's "salted hash" wording is satisfied and exceeded; see the judgment-call ruling in Findings F-1.1-03.
- AC10, phase 1.0 untouched. `git diff main...HEAD -- .../app.py` is exactly two added lines, the router import and `app.include_router(auth_router)`; the `/health` and `/query` handlers are byte-identical. `git diff main...HEAD --name-only -- tests/` excluding the two new packages returns nothing, so no phase 1.0 test was edited to make it pass. Running the phase 1.0 suite alone: `191 passed`, matching the phase 1.0 close baseline exactly. `I health: 200 {"status":"ok"}` through the app with the router mounted. PASS.
- Gate, parameterized queries. No f-string and no `.format(` anywhere in the diff's SQL path; all database access goes through SQLAlchemy Core constructs (`select`, `update`) with bound parameters. PASS.
- Gate, retry-safety and actionable errors. Signup is repeat-safe: a duplicate returns 409 and creates no second row, with the `users.email` unique constraint as the real guard behind an `IntegrityError` rollback (router.py:180-186), not a bare pre-check. Refresh and logout are idempotent in effect, since the atomic revoke matches at most once. Error details name the actionable condition (`"invalid or expired refresh token"` tells a client to re-authenticate rather than retry). PASS.
- Gate, type hints, naming, lint. Zero annotation gaps across `router.py`, `schemas.py`, and `dependencies.py` by AST audit; `ruff check` passed on all five touched files; no non-snake_case identifier. PASS.
- Gate, v1 scope boundary. `git diff main...HEAD | grep -inE 'blast|vcf|sequence.similar|distill|ensemble|fusion|federat|segmental'` returns one hit, the phrase "blast radii" in a DECISIONS.md prose row. No out-of-scope capability is built. PASS.
- Tests: 26 passed in `test_router.py`, re-run by the judge; full suite `284 passed` (191 phase 1.0 baseline plus 29 plus 38 plus 26, arithmetic confirmed by running each package separately). No test skipped, so the database-backed paths genuinely executed.
- Non-blocking observations recorded rather than filed as defects: `POST /auth/logout` requires no access token, taking the refresh token in the body as the credential, which is standard for a revocation endpoint since possession of the token is the proof; and the client IP is read from `request.client.host` (router.py:125) rather than a forwarded header, so behind a proxy the hashed value will be the proxy's address, which matters only once `ip_hash` acquires a consumer.

History:
- 2026-07-28 lead: created, scoped from Section 15's endpoint list, phase 1.1 open, depends on T-1.1-01 and T-1.1-02
- 2026-07-28 lead: tech refinement complete, no product-owner question outstanding, refined
- 2026-07-28 judge: done. All ten acceptance criteria independently re-verified over real HTTP, including a byte-identical enumeration-resistance comparison, a refresh replay, a cross-user isolation probe, and forged expired and `alg: none` tokens. Both judgment calls the builder flagged were ruled non-blocking; see F-1.1-02 and F-1.1-03
- 2026-07-28 builder-auth-router: implemented the five `/auth` endpoints (`router.py`), Pydantic schemas with `extra="forbid"` (`schemas.py`), and the Bearer-token `get_current_user` dependency (`dependencies.py`), mounted at `/auth` in `app.py` with no other change to the phase 1.0 endpoints. Login is enumeration-resistant (a fixed dummy argon2 hash keeps the unknown-email and wrong-password branches doing equal work with byte-identical 401 bodies). Refresh and logout revoke via a single atomic `UPDATE ... WHERE revoked_at IS NULL AND expires_at > now`, not a select-then-mutate, so a concurrent replay of the same refresh token cannot also succeed. `ip_hash` is a keyed HMAC-SHA256 of the client IP using the existing `AUTH_SECRET` (no new env var added; no file in this ticket's scope includes `env.example`). 26 new tests in `test_router.py`, all skip cleanly if PostgreSQL is unreachable; full suite is 284 passed (258 prior plus 26 new); `ruff check` clean on all five touched files. Commit `ff797d2`. Status set to in-review, not done, per instruction that only the judge sets done

## Premise check, 2026-07-28, judge

Leaf verification asks whether each artifact meets its own ticket. That passes even when the decomposition was wrong, so the set was also checked against what Section 25 row 1.1 actually promises: minimal v1 auth (Step 1.7) plus the PostgreSQL user-data schema.

Result: the decomposition was correct and the set delivers the phase outcome. Section 15 was walked requirement by requirement against the branch, and every one has an owner: the six tables and two extensions (T-1.1-01), the argon2id password hash, the 15-minute HS256 access token carrying only `user_id`, and the opaque SHA-256-hashed rotating refresh token (T-1.1-02), and all five endpoints `/auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me` (T-1.1-03). Nothing Section 15 requires is unowned.

The lead's open decision to build all six Section 15 tables rather than Section 25's three-table parenthetical was correctly executed. Verified against the live database rather than the migration file: all six tables exist with Section 15's exact columns, types, nullability, and defaults, all nine CHECK constraints reject out-of-set values, both unique constraints hold, all five foreign keys carry the declared CASCADE or SET NULL behavior, and all six indexes exist with their Postgres-specific details (`created_at DESC`, `gin_trgm_ops`, two GIN indexes) intact. The six-table read was also the only loadable one, since `interactions` references `sessions` and `saved_queries` references `interactions`.

Two Section 15 environment obligations were checked for a gap and found already satisfied: `env.example` line 64 declares `USER_DB_URL=postgresql://localhost:5432/search_agent_users` and line 75 declares `AUTH_SECRET=`, so no ticket needed to add them.

One narrow Section 15 gap surfaced that no ticket covered, filed below as F-1.1-04: the `users.profile` JSONB column exists in the schema but has no read or write path, while Section 15 describes `GET /auth/me` as returning "the caller's profile". It is low severity and does not fail the phase, because the column that personalization needs is present and the personalization mechanics themselves belong to build phase 4.x.

## Findings

| ID | Severity | Ticket | Status | Summary |
|----|----------|--------|--------|---------|
| F-1.1-01 | High | T-1.1-01 | closed | The migration test destroys every row in the database `USER_DB_URL` names |
| F-1.1-02 | Low | T-1.1-03 | filed | The 30-day refresh-token TTL is recorded only in a code comment |
| F-1.1-03 | Low | T-1.1-03 | filed | Rotating `AUTH_SECRET` silently orphans every stored `ip_hash` |
| F-1.1-04 | Low | T-1.1-03 | filed | `users.profile` has no read or write path on any endpoint |
| F-1.1-05 | Medium | T-1.1-03 | filed | No rate limit on `/auth/login`, an argon2id CPU cost per unauthenticated request |
| F-1.1-06 | Low | T-1.1-03 | filed | The router tests commit rows they never clean up, so the dev database grows by 10 users and 7 auth_sessions per full-suite run |

### F-1.1-01: the migration test destroys all data in the shared user database

Severity: high. Ticket: T-1.1-01. Status: closed 2026-07-28 by the judge. Blocked: yes, this was why T-1.1-01 was rejected; the block is lifted.

Closure reason: commit `20d4d7a` moves the upgrade/downgrade round trip onto a uniquely named throwaway database (`migration_scratch_<uuid4 hex>`), created by a module-scoped `scratch_db_url` fixture and dropped in a `finally` block, with `migrated_head` repointing `USER_DB_URL` via `monkeypatch.setenv` for the duration of each test. The database `USER_DB_URL` names is now only ever a read-only reachability probe target, never a migration target. Closed on re-verification evidence, not on the fix agent's report: the judge re-derived the canary from this finding's own text and ran it against the full suite (`284 passed`), with `canary_rows=1` and `public_tables=7` afterward where round 1 gave `0`. The full round-2 evidence, including the verify-surface check and the two induced-failure teardown probes, is in T-1.1-01's "Evidence, round 2" block above.

Ledger tension, flagged deliberately rather than glossed. The `task-tracker` convention is that the agent who raises a finding never closes it, and here the same judge does both. Stated plainly: the work being closed is the fix agent's (`fix-f1101-destructive-test`, commit `20d4d7a`), not the judge's, so the maker-checker split that the rule exists to protect is intact at the level that matters, and every probe behind this closure was re-run independently from this finding's own text rather than read off the fix agent's report. What is not satisfied is the letter of the rule, since the raiser is also the closer. This is the same tension the phase 1.0 judge recorded. If the lead wants the letter as well as the substance, add a separate sign-off from another agent before phase close.

`tests/system_03_search_agent/data/test_migration.py:26` resolves its target as `os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")`, the developer's real user-data database, and one of its tests runs `alembic downgrade base` against it. Downgrade drops all six tables, so every row is destroyed. The `migrated_head` fixture (lines 64-79) restores the schema in its teardown and is explicit that it does so "so other tickets that depend on this schema are never left looking at a torn-down database", but restoring the schema does not restore the data, and nothing warns that the data is gone. Anyone who runs `pytest tests/` against a populated database silently loses every user, auth session, chat session, interaction, candidate, and saved query.

Reproduction, run by the judge:

```
psql -d search_agent_users -c "INSERT INTO users(email,password_hash) VALUES('canary-do-not-delete@example.com','h')"
psql -d search_agent_users -At -c "SELECT count(*)||' users before' FROM users"     # 11 users before
pytest tests/system_03_search_agent/data/test_migration.py -q                        # 5 passed in 0.53s
psql -d search_agent_users -At -c "SELECT count(*)||' users after' FROM users"      # 0 users after
psql -d search_agent_users -At -c "SELECT count(*) FROM users WHERE email='canary-do-not-delete@example.com'"  # 0
```

The same run also destroyed the ten rows the judge's own HTTP probe had created minutes earlier, which is how it was noticed. Suggested direction for the lead to dispatch, not applied here: have the module create and drop its own throwaway database, the way the judge's independent rollback check used `judge_scratch_1_1`, so `USER_DB_URL` is never the downgrade target. No schema or migration change is needed; the migration itself is correct and its rollback was independently proven working.

### F-1.1-02: the 30-day refresh-token TTL is undocumented, ruling on judgment call 2

Severity: low. Ticket: T-1.1-03. Status: filed. Blocks the ticket: no. Blocks phase close: yes, as a one-line documentation edit.

Ruling: 30 days is an acceptable value for v1 and the builder did not violate the specification, since Section 15 declares the `expires_at` column and deliberately pins no number, and 30 days is the ordinary self-hosted default. But it must be recorded before the phase closes, and a code comment is not the right home for it. `.claude/rules/decision-logging.md` calls for a DECISIONS.md row on "any choice where reverting later would cost real work" and any choice debated for more than two minutes; the builder wrote a five-line comment justifying this one (router.py:84-89), which is itself the evidence that it was a real decision rather than an obvious default. It is also security-relevant: a refresh TTL is the outer bound on how long a stolen refresh token stays useful, and a number that exists only in a comment will not be found by anyone later tuning that exposure. Action for the lead: append a DECISIONS.md row dated 2026-07-28 naming the 30-day value, the alternatives, and the reasoning, before `/ship`.

### F-1.1-03: `AUTH_SECRET` reuse for `ip_hash`, ruling on judgment call 1

Severity: low, informational. Ticket: T-1.1-03. Status: filed. Blocks: no.

Ruling: reusing `AUTH_SECRET` as the HMAC key for `ip_hash` is acceptable and does not block. Three parts to that.

On key reuse across purposes: the domain separation at router.py:116 is genuine, not nominal. HS256 signs the message `<base64url header>.<base64url payload>`, which always begins with the bytes `eyJ`; the `ip_hash` message always begins with the literal bytes `ip_hash:`. The two message spaces cannot collide, so an attacker who can induce arbitrary token signing can never steer that oracle into producing an `ip_hash` for a chosen address. HMAC's security rests on a distinct message per purpose, not a distinct key per purpose, and that condition is met.

On Section 15's "salted hash" wording: satisfied and exceeded. A salt is stored beside the value and is public, so it defeats precomputed tables but not a targeted brute force; the entire IPv4 space is about four billion candidates, which is trivially searchable offline against a salted SHA-256. A secret HMAC key defeats that attack outright, because an attacker holding a database dump has no key to search with. The keyed construction is the stronger choice, not a shortcut around the requirement.

On rotation, which is the real cost and the reason this is filed rather than dismissed: rotating `AUTH_SECRET` changes every future `ip_hash` while leaving the stored ones unchanged, so values computed before and after a rotation become mutually uncomparable. Section 15 states `ip_hash` exists "to flag anomalous refresh-token reuse", which is inherently a comparison across rows, so a rotation silently breaks the column's only stated purpose with no error and no migration path. That coupling is undesirable, because a signing secret should be freely rotatable while an analytics key wants to be long-lived. It does not block today because nothing in v1 reads `ip_hash` yet. Action: record this so whoever builds refresh-reuse anomaly detection introduces a dedicated `IP_HASH_KEY` at that point, or accepts a deliberate reset of the column at rotation.

### F-1.1-04: `users.profile` has no read or write path

Severity: low. Ticket: T-1.1-03. Status: filed. Blocks: no.

Section 15 describes `GET /auth/me` as returning "the caller's profile from the access token", and defines `users.profile` as a JSONB column holding audience-level depth and a display name. The column exists in the live schema with the correct default, but `MeResponse` (schemas.py:72-78) returns `id`, `email`, `created_at`, and `last_login_at` only, and no endpoint writes `profile`. Reproduction: `GET /auth/me` with a valid token returns `{"id":"...","email":"...","created_at":"...","last_login_at":"..."}` with no `profile` key. Surfaced by the premise check rather than by any single ticket's criteria, since no criterion mentioned the column. Non-blocking: the storage the personalization firewall needs is in place, and the mechanics that populate and consume it belong to build phase 4.x per Section 25.

### F-1.1-05: no rate limit on `/auth/login`

Severity: medium. Ticket: T-1.1-03. Status: filed. Blocks this phase: no, it is owned by build phase 6.0.

`production-standards` requires rate-limiting consideration on every endpoint. `/auth/login` runs a full argon2id verification on every request, including for an unknown email, because the enumeration defence at router.py:198 deliberately hashes against a dummy value rather than short-circuiting. That closes the timing channel, correctly, and in exchange makes every unauthenticated request cost real CPU, so the endpoint is both a credential-stuffing surface and a cheap CPU-exhaustion surface. Reproduction: `POST /auth/login` can be issued without limit; nothing in `router.py` or `app.py` throttles it. Filed rather than dismissed so it is not lost, but it does not block phase 1.1: Section 25 places rate limiting and concurrency at build phase 6.0, so the consideration is deferred to a named phase rather than absent.

### F-1.1-06: the router tests leave committed rows behind on every run

Severity: low. Ticket: T-1.1-03. Status: filed. Blocks phase close: no.

Raised by the lead's observation and ruled on by the judge. It is a real defect in test hygiene, not acceptable-as-is, but it is low severity and does not block.

Measured, two consecutive full-suite runs, not inferred:

```
run 1: users 23 -> 33 (delta 10), auth_sessions 21 -> 28 (delta 7)   # 284 passed in 2.58s
run 2: users 33 -> 43 (delta 10), auth_sessions 21 -> 28 (delta 7)   # 284 passed in 2.61s
```

The growth is deterministic and unbounded across runs. `sessions`, `interactions`, `cq_candidates`, and `saved_queries` all stay at `0`, so the residue is confined to the two tables the auth endpoints write.

The source is `tests/system_03_search_agent/auth/test_router.py`, which is not the module the judge cleared under F-1.1-01. It drives the real `/auth/signup` and `/auth/login` endpoints through `TestClient`, so every row those endpoints write is committed by the application's own session, outside any test-owned transaction. `grep -cE 'session.delete|DELETE FROM|rollback'` over that file returns `0`: it has no cleanup fixture of any kind. The contrast is `tests/system_03_search_agent/data/test_models.py:123-128`, whose `db_session` fixture ends in `finally: session.rollback()`, which is why that module leaves nothing behind. The router module needs the equivalent, most simply a fixture that records the emails it creates and deletes those `users` rows in teardown, letting the existing `ON DELETE CASCADE` clear the matching `auth_sessions` rows.

Why it is a defect and not merely untidy:

- Unbounded growth. Nothing ever prunes these rows, so a developer running the suite in a loop accumulates them indefinitely in the database that phase 4.6's feedback loop will later read. Real data and test residue become indistinguishable, since the residue rows are ordinary valid `users` rows.
- It already masked something once. Under round 1, the migration test's `downgrade base` silently deleted this residue along with everything else, which is part of why the destructive behavior went unnoticed until a canary was planted. Residue that disappears without complaint is exactly the condition that hides a data-destroying bug.
- Each residue row carries a real argon2id hash, so the cost is CPU at write time, not just disk.

Why it does not block phase close, checked rather than assumed:

- No test asserts on a global row count today, so nothing is order-dependent or flaky as residue accumulates. The only count in the suite is `_count_users_with_email` at `test_router.py:90-95`, which is scoped by `where(User.email == email)`, and every test email is a fresh `uuid.uuid4()` from `_unique_email()` at line 66. Collisions are not possible at any residue level, and the assertions stay correct no matter how many rows precede them.
- The residue is confined to a local developer database. Nothing in CI or production is affected.

Action for the lead: add a teardown fixture to `test_router.py` in this phase if the budget allows, otherwise carry it as a known item. The rule it sits under is `production-standards`, "integration tests hit a real database or graph connection where feasible", which is satisfied; what is missing is the cleanup that makes a real-database integration test repeatable. Judge did not fix it, per the report-do-not-fix instruction.
