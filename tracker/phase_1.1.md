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

Status: in-review
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
- (filled at close by the judge)

History:
- 2026-07-28 lead: created, scoped from Section 15, phase 1.1 open
- 2026-07-28 lead: tech refinement complete, six-table scope decided and recorded above, environment pre-verified, no product-owner question outstanding, refined
- 2026-07-28 builder-user-data-schema: built the six SQLAlchemy models (base.py, models.py, session.py) and the hand-written 0001_user_data_schema Alembic migration; created the search_agent_users database; verified upgrade head and downgrade base against real local PostgreSQL; 220 tests passing (191 prior plus 29 new); ruff and pip-audit clean on new code; commit fcd3db0; status set to in-review for judge sign-off

### T-1.1-02: Auth primitives and the ecdsa CVE resolution

Status: in-review
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
- [ ] `ecdsa` is absent from the installed dependency tree, verified by `pip show ecdsa` reporting not found, and `pip-audit` reports no Critical or High finding against the auth dependencies
- [ ] A password verifies against its own argon2id hash and fails against any other password, and the stored hash is never equal to the plaintext
- [ ] Neither the plaintext password nor the resulting hash appears in any log record or exception string raised by the password module
- [ ] An access token decodes back to the `user_id` it was minted for, is rejected once past its 15-minute expiry, and is rejected when verified with a different secret
- [ ] An access token's decoded claims contain `user_id` and standard JWT registered claims only, carrying no email, no display name, and no other profile field
- [ ] A token presented with `alg: none`, or signed with any algorithm other than HS256, is rejected rather than accepted
- [ ] A refresh token is an opaque random string carrying at least 32 bytes of entropy, is not parseable as a JWT, and differs across successive calls
- [ ] A refresh token verifies against its own SHA-256 hash and fails against the hash of any other token, and the raw refresh token is never what the hashing function returns for storage
- [ ] With `AUTH_SECRET` unset in the environment, minting or verifying a token raises an error rather than falling back to a default, empty, or hardcoded secret

Breakdown:
- [x] Swap `python-jose[cryptography]` for the chosen JWT library in `requirements.txt` and `pyproject.toml`, reinstall, confirm `ecdsa` is gone
- [x] argon2id password hash and verify
- [x] HS256 access-token mint and verify, with expiry and algorithm pinning
- [x] Opaque refresh-token generation and SHA-256 hashing
- [x] Tests: valid, invalid, expired, tampered, wrong-secret, wrong-algorithm, and missing-secret paths for each primitive

Evidence:
- (filled at close by the judge)

History:
- 2026-07-28 lead: created, scoped from Section 15's token model, phase 1.1 open
- 2026-07-28 lead: tech refinement complete, researcher established that `ecdsa` is a core (not extra-gated) requirement of `python-jose` so it cannot be excluded in place, library swap authorized as a tactical decision under bossman mode and logged to DECISIONS.md, refined
- 2026-07-28 builder-auth-primitives: implemented all three primitives (argon2id password hashing in `auth/passwords.py`, HS256 access tokens and opaque SHA-256-hashed refresh tokens in `auth/tokens.py`), swapped `python-jose[cryptography]` for `PyJWT` plus `argon2-cffi` in `requirements.txt` and `pyproject.toml`, uninstalled `ecdsa`/`python-jose` from the shared venv and reinstalled the new pair. All nine acceptance criteria proven by 38 new tests (10 in `test_passwords.py`, 28 in `test_tokens.py`); full suite is 229 passed (191 prior plus 38 new), `pip show ecdsa` reports not found, `pip-audit` reports no known vulnerabilities. Commit `465291e`. Status set to in-review, not done, per instruction that only the judge sets done

### T-1.1-03: Auth router and app wiring

Status: todo
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
- [ ] `POST /auth/signup` with an unused email returns a success status and creates exactly one `users` row; the same email again returns 409 and creates no second row
- [ ] `POST /auth/login` with correct credentials returns both an access token and a refresh token and updates `users.last_login_at`
- [ ] `POST /auth/login` with a wrong password returns 401 with no token in the body, and its response is indistinguishable between an unknown email and a known email with a wrong password, so the endpoint does not disclose which emails are registered
- [ ] `POST /auth/refresh` with a valid refresh token returns a new access token and a new refresh token, and replaying the presented refresh token afterwards returns 401, so rotation actually invalidates the old one
- [ ] `POST /auth/logout` sets `revoked_at` on the caller's `auth_sessions` row, and a refresh with that token afterwards returns 401
- [ ] `GET /auth/me` returns the caller's profile for a valid access token, and returns 401 for a missing, malformed, or expired token
- [ ] Every request body is validated through a Pydantic model with `extra="forbid"`, so an unknown field returns 422 rather than being silently ignored
- [ ] No response body from any `/auth` endpoint contains `password_hash`, `refresh_token_hash`, or any other user's data
- [ ] `auth_sessions.ip_hash` holds a salted hash, and the raw client IP address appears in no column and no log line
- [ ] Mounting the auth router leaves `GET /health` and `POST /query` behaving exactly as they did at the close of phase 1.0, verified by the phase 1.0 tests still passing unchanged

Breakdown:
- [ ] Pydantic request and response schemas with `extra="forbid"`
- [ ] The five endpoints wired to the models from T-1.1-01 and the primitives from T-1.1-02
- [ ] Access-token dependency for authenticated routes
- [ ] Router mounted at `/auth` in `app.py`
- [ ] Tests: valid, invalid, missing, and null input on all five endpoints, plus the rotation, revocation, and enumeration-resistance paths

Evidence:
- (filled at close by the judge)

History:
- 2026-07-28 lead: created, scoped from Section 15's endpoint list, phase 1.1 open, depends on T-1.1-01 and T-1.1-02
- 2026-07-28 lead: tech refinement complete, no product-owner question outstanding, refined

## Findings

No findings filed yet. The adversary pass runs at stage 8 of the build cadence, after the judge.
