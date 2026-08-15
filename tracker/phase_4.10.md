# Build phase 4.10: the anonymous run path and the guest allowance

Branch: `phase/4.10-guest-allowance`
Depends on: 1.1 (merged, PR #6), 4.0 (merged, PR #39)
Opened: 2026-08-15
Status: BUILD COMPLETE. Five review rounds run: a judge round (FAIL), an adversary round, three fix rounds, and a re-review (FAIL). A narrow independent verification of the newest security code is the last round. 26 findings closed including four criticals; ten carried with a named owner each, in "Carried open, with an owner each" below.

Gates at close: Python 2593 passed with the 6 known live-network-gated failures carried since build phase 4.0, this phase's own gate at 32 clauses, all green, frontend 177, Playwright 30 of 30 including the full axe sweep, typecheck and production build clean, `ruff` at its 5 pre-existing errors, alembic revisions 0003 through 0005 each applied and rolled back against the live database.

One number worth stating plainly, since this phase's whole argument rests on it: an anonymous caller could start 200 paid pipelines in 1.68 seconds and take the product offline for everyone else for the rest of the day. That is now 10, and the day's shared budget is untouched.

Premise gate: `tests/system_03_search_agent/adapters/web_sse/test_phase_4_10_premise.py`. First run, 2026-08-15, before any implementation existed: 16 failed, 1 passed. The failures are the correct direction, `POST /auth/guest` returning 404 and no `system_03_search_agent.auth.guest` module to import. The single pass is recorded as VACUOUS in the test's own docstring: everything returns 401 today, so the domain-separation clause cannot yet tell "the derivation is right" from "nothing exists". The judge re-runs that one clause against a working guest path with the derivation replaced by bare `AUTH_SECRET` and watches it go red before crediting it.

Deliverable: a visitor with no account can ask a real question and get a real answer, five times, counted by the server. Split out of build phase 6.0 and pulled ahead of 4.2 to 4.7 by product-owner directive, 2026-08-14, because until it exists nobody can use this product without creating an account first.

## Table of contents

- [The premise](#the-premise)
- [What the ground truth actually is](#what-the-ground-truth-actually-is)
- [Design decisions taken at decomposition](#design-decisions-taken-at-decomposition)
- [Tickets](#tickets)
- [Builder partition](#builder-partition)
- [What is deliberately not in this phase](#what-is-deliberately-not-in-this-phase)
- [Findings](#findings)
- [Carried open, with an owner each](#carried-open-with-an-owner-each)

## The premise

> A caller the server has never seen can complete five real, cited runs without an account, the server alone decides when the fifth is spent, and no guest can read, stop, or spend another caller's runs.

Both halves are load-bearing, and this is a guardrail-shaped phase, so the gate needs two arms the way build phase 3.0's did. Refusing every guest scores one hundred percent on every attack test that will ever be written here and destroys the product. Admitting every guest passes every admission test and gives away the system. Only one of those is caught by an attack test, which is why the gate's admit arm is written first.

## What the ground truth actually is

Probed rather than reasoned about, 2026-08-14 and re-confirmed at this phase's open:

| Claim | State today | Evidence |
|-------|-------------|----------|
| The API accepts an anonymous run | It does not. All four `/v1/query` endpoints depend on `get_current_user` | `adapters/web_sse/app.py:207,245,389,486` |
| A guest path exists anywhere in `src/` | It does not | No `guest` symbol in `src/` |
| Run ownership tolerates a caller with no `users` row | `RunEntry.user_id` is already `str \| None`, but every reader compares it to `str(current_user.id)` | `core/run_registry.py:188`, `adapters/web_sse/app.py:235` |
| The data model tolerates an anonymous interaction | It does. `interactions.user_id` and `sessions.user_id` are both nullable by design | `data/models.py:140,163` |
| The allowance counter is honest today | It is not. `used` is React state in `App.tsx`, reset on reload, and never reaches a server | `frontend/src/App.tsx`, `setUsed((n) => n + 1)` |
| The account menu's search-limit copy is true | It is not. It says "unlimited searches" against a shipped, enforced 100/day cap | `frontend/src/components/shell/AccountMenu.tsx:173`, `harness/cost_control.py:143` |

The UI half of the allowance, the five dots and the wall, is already built and styled (`components/guest/GuestAllowance.tsx`). This phase does not design it. It gives it something true to render.

## Design decisions taken at decomposition

Each of these is a lead decision made at stage 3 rather than left for a builder to improvise, because a builder resolving it differently in two files is exactly the cross-file seam the build phase 3.1 fix round hit. Each is logged to `DECISIONS.md` at phase close.

### 1. The guest identity is a signed token, and its key is domain-separated from the access-token key

Product-owner decision, 2026-08-14: a signed guest token minted on first visit, chosen with a prototype mindset. It is clearable, and anyone who clears it gets five more searches. That is accepted, not overlooked, and the gate asserts it as known behaviour so it is documented rather than discovered later.

The signing key is NOT `AUTH_SECRET` directly. It is `HMAC-SHA256(AUTH_SECRET, b"guest-token-v1")`. Two reasons, and the second is the one that matters:

- No new required env var, so no new way to misconfigure a deployment and no `.env` change that every test has to learn about.
- Cryptographic domain separation. A guest token and an access token are then unforgeable as each other even if the claim checks below were wrong. Claim checks alone would be sufficient today (`decode_access_token` requires a `user_id` claim, which a guest token does not carry) but that is one edit away from not being true, and token confusion between two principal classes is the single highest-severity defect available in this phase.

Guest token claims: `guest_id`, `typ: "guest"`, `iat`, `exp`. TTL 7 days, not the access token's 15 minutes: a guest has no refresh path, and a 15-minute guest identity would silently hand a visitor a fresh allowance every 15 minutes, which defeats the count.

### 2. Owner ids are namespaced, and the registered-user id keeps its own field

`RunEntry` gains `owner_id`, a namespaced string, `user:<uuid>` or `guest:<uuid>`. Every ownership comparison reads `owner_id` and nothing else.

`RunEntry.user_id` stays exactly what it is, the registered user's bare UUID string or `None`, because it is what `is_operator_user()` reads and what an `interactions.user_id` write will need at build phase 4.6. A namespaced string must never reach either. A guest's `user_id` is `None`, and `is_operator_user` must treat `None` as not an operator: a guest can never be an operator, and the phase gate asserts it.

Two fields that could drift is a real cost, taken deliberately over the alternative, which is a namespaced string leaking into a UUID column.

### 3. The allowance is counted by a conditional atomic UPDATE, never a read-then-write

New table `guest_sessions`, alembic revision `0003`. The spend is one statement:

```sql
UPDATE guest_sessions
   SET runs_used = runs_used + 1, last_seen_at = now()
 WHERE id = :guest_id AND revoked_at IS NULL AND runs_used < :cap
RETURNING runs_used
```

No row returned means the allowance is spent or the session is revoked. A read-then-write lets two concurrent requests both observe four and both take the fifth, which is a 6-search allowance reachable by anyone who can open two tabs. The gate fires six concurrent requests at the boundary and asserts at most five succeed.

`interactions` is not the counter. Nothing writes that table yet (F-2.0-04), so counting there would be counting zero, and F-2.0-04 is build phase 4.6's to close.

### 4. Migration moves what actually exists, and says so

Product-owner decision, 2026-08-15. On signup or login while holding a guest token, the server re-points that guest's live runs to the new user and revokes the guest session. That is honest and testable.

It is NOT durable cross-reload history. Nothing persists a run today: the `RunRegistry` is in-memory and evicts past a retention window, and the browser's history list is React state. The sign-in wall's promise, "Your history moves with you", therefore overstates what ships here, and the copy is corrected in this phase rather than left to overclaim. Durable history is build phase 4.6's, filed as a finding below rather than absorbed silently.

### 5. Two refusals, two status codes, because they mean different things

Settled while writing the premise gate, which is the argument for writing it first: the decomposition originally said the sixth run returns 429, and that is wrong.

- Allowance spent: `403`, carrying the machine-readable reason `guest_allowance_exhausted`. The caller is authenticated as a guest and is not permitted more. Retrying later does not help, so a 429 with a `Retry-After` would be a lie the UI would then repeat to the user as "try again soon".
- Concurrent-run cap, F-4.0-A-10: `429` with a real `Retry-After`. This one genuinely is transient. Finishing a run frees a slot.

The UI branches on the reason string, not on the bare 403, so the sign-in wall appears for this specific case rather than for any refusal.

### 6. Wire shapes, fixed here so two builders cannot invent two of them

```
POST /auth/guest  -> 201  {guest_token, guest_id, used, total}
GET  /v1/allowance -> 200 {kind: "guest"|"user", used, total, counted}
POST /auth/signup  <- optional body field `guest_token`
POST /auth/login   <- optional body field `guest_token`
```

`counted` is the honesty field. It is `true` for a guest, whose count is real, and `false` for a registered caller, whose count reads a structural zero because nothing writes `interactions` rows yet (F-2.0-04). Rendering an uncounted zero as a count is the same dishonesty class as the client-side counter this phase removes.

The guest token travels as a body field on signup and login rather than in the `Authorization` header, because those two endpoints already treat that header as absent and giving it a second meaning there is how a token-confusion bug gets written.

### 7. The run-creation bound covers both principal classes

F-4.0-A-10 names the anonymous caller, but the bound belongs on the principal, not on the anonymity. A registered user creating unbounded concurrent runs is the same resource exhaustion with a `users` row attached. One cap, read from the principal, applied at `create_run`.

### 8. Anonymous spend is bounded by a daily budget, with an IP throttle in front of it

Added 2026-08-15 after the adversary round, product-owner decision the same day. This is a correction to design decision 7, which was wrong in a way worth stating plainly rather than quietly amending.

Decision 7 said the run-creation bound "belongs on the principal, not on the anonymity". That is true and it is not sufficient, because a guest principal costs nothing to create. `POST /auth/guest` is unauthenticated and takes no body, so keying a cap on `owner_id` keys it on a variable the caller controls the supply of. Measured by the adversary: 40 paid pipelines accepted in 0.25 seconds, 157 per second, from a caller with no account, while a single guest is correctly capped at five.

Nothing was behind it. Both existing cost caps are structurally dead for a guest: `check_user_daily_query_cap` is skipped when `query.user_id is None`, which is every guest by decision 2, and `check_system_daily_cost_cap` sums `interactions.cost_usd` while nothing writes that table (F-2.0-04, build phase 4.6). So the system-wide dollar cap reads zero on every call and can never fire.

The product owner's 2026-08-14 acceptance ("anyone who clears it gets five more searches") accepted a person clearing browser storage. It did not accept a script minting identities in parallel, and the router's own comment arguing the two are equivalent is the conflation this finding names.

Two controls, and only one of them is the backstop:

- The backstop: a system-wide daily cap on anonymous runs, `ANON_DAILY_RUN_CAP`, read through `harness/cost_control.py` the same way every other cap is, never a second hardcoded copy. It bounds total dollars regardless of how many identities exist or where they come from, which is the property the per-principal cap cannot have. A new `guest_daily_usage(day, runs_used)` row per UTC day, spent by the same single conditional `UPDATE ... RETURNING` decision 3 requires.
- Defense in depth: a per-IP throttle on minting. It stops casual abuse and the connection-pool exhaustion of F-4.10-A-02, where 60 concurrent mints made a registered login take 30.1 seconds instead of 0.098. It is explicitly NOT the bound, because a rotating source defeats it.

Four constraints on the implementation, each because getting it wrong is worse than not having it:

- The two spends, per-guest and per-day, happen in ONE transaction. A per-guest spend that commits while the daily spend fails charges a visitor for a run they never got.
- The IP comes from the connection, never from a client-supplied `X-Forwarded-For`, which an attacker sets freely. Behind a real proxy this needs the proxy's own real-IP configuration, and that is a deployment note, not a code fallback.
- No raw IP is stored. `auth/router.py`'s existing `_hash_ip` already does keyed HMAC-SHA256 with its own domain separator; reuse it.
- `GET /v1/allowance` must reflect the daily bound too. This is F-4.10-A-03's lesson generalized: the reporting path and the enforcement path must agree about what is available, or the five dots promise a search the next request refuses.

The refusal is a 429 with `Retry-After` set to the seconds remaining until UTC midnight, and a message saying that signing in works right now. Unlike a spent per-guest allowance, this one genuinely is transient, so 429 is the honest code here where 403 was the honest code there.

## Tickets

### T-4.10-01: guest token primitives

Status: todo
Refine: refined
Branch: `phase/4.10-guest-allowance`
Depends on: none
Spec: Section 15's token design, extended. `auth/tokens.py` is the pattern to match.

Acceptance criteria:
- [ ] `auth/guest.py` exposes `mint_guest_token(guest_id)` and `decode_guest_token(token)`
- [ ] The signing key is `HMAC-SHA256(AUTH_SECRET, b"guest-token-v1")`, derived at call time, never cached at import, matching `tokens.py`'s own env discipline
- [ ] `decode_guest_token` pins HS256 explicitly and requires `exp`, `typ == "guest"` and `guest_id`; a token missing or misdeclaring `typ` is rejected
- [ ] `decode_guest_token` rejects an `exp` further out than the 7-day policy plus 60s skew, enforcing the contract independently of the minter, exactly as `decode_access_token` does
- [ ] A valid ACCESS token is rejected by `decode_guest_token`, and a valid GUEST token is rejected by `decode_access_token`. Both directions tested
- [ ] No token value, decoded payload, or derived key appears in any log record or exception string
- [ ] Tests cover valid, tampered, expired, wrong-key, wrong-`typ`, missing-claim, and null input

Breakdown:
- [ ] Key derivation
- [ ] Mint
- [ ] Decode with the independent contract check
- [ ] Cross-type rejection tests

Evidence:
- (filled at close)

History:
- 2026-08-15 lead: created, scoped from design decision 1

### T-4.10-02: the `guest_sessions` table and its atomic spend

Status: todo
Refine: refined
Depends on: none
Spec: Section 15's schema conventions. `alembic/versions/0002_auth_hardening.py` is the pattern to match.

Acceptance criteria:
- [ ] `guest_sessions` declared in `data/models.py`: `id` UUID PK, `created_at`, `last_seen_at`, `runs_used` INT NOT NULL DEFAULT 0, `revoked_at` nullable, `migrated_to_user_id` nullable FK `users.id` ON DELETE SET NULL
- [ ] A `CheckConstraint` holds `runs_used >= 0`
- [ ] Alembic revision `0003` hand-written from the model, with a working `downgrade`, and the expand-contract rollback stated in its docstring per `production-standards`
- [ ] A repository function performs the spend as ONE conditional `UPDATE ... RETURNING`, never a `SELECT` followed by an `UPDATE`
- [ ] The spend returns a three-state result the caller can branch on: spent (with the new count), exhausted, revoked-or-unknown. Not a bare bool
- [ ] A test drives concurrent spends at the cap boundary and asserts the cap holds. If the test harness cannot produce true concurrency against the configured database, the test asserts the SQL shape is conditional rather than asserting nothing, and says so in its own docstring
- [ ] Tests cover valid, invalid, and null input

Breakdown:
- [ ] Model
- [ ] Migration with downgrade
- [ ] Atomic spend
- [ ] Concurrency test

Evidence:
- (filled at close)

History:
- 2026-08-15 lead: created, scoped from design decision 3

### T-4.10-03: the principal resolver and the four query endpoints

Status: todo
Refine: refined
Depends on: T-4.10-01, T-4.10-02
Spec: Section 13.1

Acceptance criteria:
- [ ] A `Principal` type carries `owner_id` (namespaced `user:<uuid>` or `guest:<uuid>`), `user_id` (bare UUID string or `None`), and `kind`
- [ ] `get_caller` resolves a `Principal` from either an access token or a guest token, and returns 401 with ONE detail string for every failure mode, so no failure discloses which check tripped, matching `resolve_user_from_bearer_token`
- [ ] All four `/v1/query` endpoints accept a guest caller
- [ ] `_get_owned_run` compares `entry.owner_id` and nothing else. The 404-before-403 ordering is unchanged
- [ ] A guest cannot read, stop, or export citations for another guest's run, nor for any user's run, and the reverse
- [ ] `is_operator_user` is never called with a namespaced id, and a guest is never an operator. Asserted directly
- [ ] A guest token is rejected by `/auth/me` and every other `get_current_user` route, unchanged 401
- [ ] `Query.user_id` continues to receive a bare UUID or `None`, never a namespaced string
- [ ] Tests cover valid, invalid, and null input on every endpoint, for both principal classes

Breakdown:
- [ ] `Principal` and `get_caller`
- [ ] `RunEntry.owner_id`
- [ ] Endpoint wiring
- [ ] Cross-principal isolation tests

Evidence:
- (filled at close)

History:
- 2026-08-15 lead: created, scoped from design decision 2

### T-4.10-04: `POST /auth/guest` and `GET /v1/allowance`

Status: todo
Refine: refined
Depends on: T-4.10-03
Spec: Section 13.1, additive within v1 per Section 2.6

Acceptance criteria:
- [ ] `POST /auth/guest` creates a `guest_sessions` row and returns `{guest_token, guest_id, used, total}` with 201. It never requires a body
- [ ] `GET /v1/allowance` returns `{kind, used, total, counted}` for the calling principal, guest or registered, per design decision 6
- [ ] For a registered caller, `total` is the real `PER_USER_DAILY_QUERY_CAP`, read from the same function the enforcement path reads, never a second hardcoded copy
- [ ] The registered caller's `used` is reported truthfully, including the fact that it reads zero today because nothing writes `interactions` (F-2.0-04). The response distinguishes "zero used" from "not counted yet" rather than presenting an uncounted zero as a count
- [ ] Both endpoints are rate-limit-considered: minting a guest token is an unauthenticated write, so it carries its own bound
- [ ] Tests cover valid, invalid, and null input

Breakdown:
- [ ] Mint endpoint
- [ ] Allowance endpoint
- [ ] Honest reporting of the uncounted registered case

Evidence:
- (filled at close)

History:
- 2026-08-15 lead: created

### T-4.10-05: bound run creation per principal, closing F-4.0-A-10

Status: todo
Refine: refined
Depends on: T-4.10-03
Spec: F-4.0-A-10, `tracker/phase_4.0.md`

Acceptance criteria:
- [ ] `create_run` refuses past a per-principal concurrent-run cap, for guests and registered users alike
- [ ] The refusal is a 429 carrying a `retry_after` estimate and naming what to do next, per `production-standards`'s retry-safety gate. Not a bare "too many requests"
- [ ] The cap is a named constant with its value justified in a comment, not a magic number
- [ ] A test reproduces the original F-4.0-A-10 shape (rapid repeated run creation from one caller) and asserts it is now bounded
- [ ] The eviction sweep from F-1.2-01's fix still works, and a completed run does not count against the cap

Breakdown:
- [ ] Per-principal accounting in the registry
- [ ] 429 with an actionable message
- [ ] Reproduction test

Evidence:
- (filled at close)

History:
- 2026-08-15 lead: created, scoped from design decision 5

### T-4.10-06: migration on signup and login

Status: todo
Refine: refined
Depends on: T-4.10-02, T-4.10-03
Spec: design decision 4

Acceptance criteria:
- [ ] `POST /auth/signup` and `POST /auth/login` accept an OPTIONAL `guest_token` BODY field, per design decision 6, and when present and valid re-point that guest's live runs to the new user's `owner_id`
- [ ] The guest session is revoked in the same transaction, so the guest token cannot start further runs afterwards
- [ ] The operation is idempotent. Replaying the same signup with the same guest token produces the same end state, per the retry-safety gate
- [ ] An invalid, expired, or already-migrated guest token does NOT fail the signup or login. Authentication is the primary operation; migration is best-effort and its failure is logged, never fatal
- [ ] A guest token belonging to a different guest cannot migrate a third party's runs
- [ ] The sign-in wall's copy is corrected to state what actually moves. The current text, "Your history moves with you", overstates it
- [ ] Tests cover valid, invalid, null, replayed, and cross-guest input

Breakdown:
- [ ] Optional guest token on both endpoints
- [ ] Re-point and revoke, one transaction
- [ ] Idempotency
- [ ] Copy correction

Evidence:
- (filled at close)

History:
- 2026-08-15 lead: created, scoped from design decision 4

### T-4.10-07: the two additive `CitationPayload` fields

Status: todo
Refine: refined
Depends on: none
Spec: Section 2.6 (additive within v1), build phase 4.9's F-4.8-D-02 and F-4.8-D-03

Acceptance criteria:
- [ ] BEFORE adding either field, print what the producer actually receives and confirm the value EXISTS. If a Layer 1 row carries no ingest date, the field is not added, the finding is filed, and the ticket closes at that. This is `attack-the-constraint`'s read-the-input-first rule, and F-3.4-T06-01 is the standing example of a field wired to data the ingest never supplies
- [ ] If the data exists: `snapshot_date` and the source entity name are added to `CitationPayload` as OPTIONAL fields defaulting to `None`, so every payload built before this phase still validates
- [ ] Each new string field carries a `maxLength`, per the multi-agent pipeline gate
- [ ] The producer populates them only where the value is real, never a fabricated or inferred date
- [ ] `frontend/src/lib/events.ts` learns both fields, so the client does not validate and then discard them, which is F-4.8-A-05's shape
- [ ] Tests cover present, absent, and malformed values

Breakdown:
- [ ] Prove the data exists
- [ ] Contract change, both sides of the wire
- [ ] Producer
- [ ] Tests

Evidence:
- (filled at close)

History:
- 2026-08-15 lead: created

### T-4.10-08: the frontend anonymous path

Status: todo
Refine: refined
Depends on: T-4.10-04
Spec: `docs/build/design/design-system/prototype/app.html`

Acceptance criteria:
- [ ] A first-time visitor mints a guest token and can ask a question. The `if (!signedIn) → wall` intercept in `App.tsx`'s `ask` is removed
- [ ] The five dots render from the SERVER's count, fetched from `GET /v1/allowance`. The `setUsed((n) => n + 1)` client counter is deleted, not merely supplemented
- [ ] The wall appears when the server refuses, never when the client guesses it should
- [ ] The guest token is passed to signup and login so migration fires
- [ ] F-4.8-P-04 does not regress: an anonymous visitor still gets NO stored-searches rail. Asserted in the gate, since this phase changes exactly the branch that defect lived in
- [ ] Typecheck clean, production build succeeds, no new axe violation

Breakdown:
- [ ] Mint and persist the guest token
- [ ] Server-driven dots
- [ ] Remove the intercept and the client counter
- [ ] Pass the token through auth

Evidence:
- (filled at close)

History:
- 2026-08-15 lead: created

### T-4.10-09: correct the search-limit copy, F-4.9-A-16

Status: todo
Refine: refined
Depends on: T-4.10-04
Spec: F-4.9-A-16

Acceptance criteria:
- [ ] `AccountMenu.tsx:173` no longer says "unlimited searches". It states the real cap, read from `GET /v1/allowance`, never a second hardcoded copy of the number
- [ ] The rail footer says the same thing as the account menu, from the same source
- [ ] `railCollapsePremise.test.tsx:439`, which asserts the false copy today, is updated to assert the true copy. It is not deleted, and its guarantee is not weakened
- [ ] If the honest answer is "not counted yet" (F-2.0-04), the copy says that rather than displaying an uncounted zero as a count

Breakdown:
- [ ] Menu copy
- [ ] Rail footer
- [ ] Update the existing assertion without weakening it

Evidence:
- (filled at close)

History:
- 2026-08-15 lead: created

### T-4.10-10: the premise gate

Status: todo
Refine: refined
Depends on: none. BLOCKS every ticket above
Owner: lead, stage 5

Acceptance criteria:
- [ ] Written and watched FAILING before any ticket above is claimed
- [ ] Two arms, admit and refuse, per the premise above
- [ ] It states its own coverage: which shapes it exercises and which it deliberately omits
- [ ] It runs the way production runs, not against a hand-picked better input

Admit arm:
- [ ] A caller with no account mints a guest token and completes a real run end to end
- [ ] Runs two through five also succeed
- [ ] The allowance count reported by the server increases by exactly one per run
- [ ] Signing up with the guest token re-points that guest's runs to the new user, and the new user can read them

Refuse arm:
- [ ] The sixth run is refused 403 carrying `guest_allowance_exhausted`, not a bare failure
- [ ] A tampered guest token, a guest token signed with `AUTH_SECRET` directly, and an expired one are each rejected 401
- [ ] A guest token is refused by `/auth/me`; an access token is refused by `decode_guest_token`
- [ ] Guest A cannot read, stop, or export citations for guest B's run
- [ ] Six concurrent requests at the boundary yield at most five successes
- [ ] A migrated, revoked guest token cannot start a new run
- [ ] A guest is never an operator, so no guest ever sees a `cost` event or an unredacted `done.total_cost_usd`

Documented, accepted behaviour, asserted so it is recorded rather than discovered:
- [ ] Clearing the guest token and minting a new one yields a fresh allowance. Product-owner decision, 2026-08-14

Stated non-coverage:
- [ ] Durable cross-reload history (build phase 4.6)
- [ ] Multi-process or multi-worker counting, since the run registry is per-process
- [ ] IP-level or device-level abuse resistance, which the clearable-token decision explicitly declines
- [ ] The registered 100/day cap actually firing, which needs F-2.0-04 closed first

Evidence:
- (filled at close)

History:
- 2026-08-15 lead: created

## Builder partition

Four builders, partitioned by write target so no two touch the same file. The lead writes the premise gate and the shared seams first and COMMITS them to the branch before dispatching: a worktree builder sees the branch's committed history, never the lead's uncommitted working tree, which is the build phase 3.5 failure recorded in `LEARNINGS.md`.

| Builder | Tickets | Writes |
|---------|---------|--------|
| A, guest identity spine | T-4.10-01, T-4.10-02, T-4.10-04, T-4.10-06 | `auth/guest.py`, `auth/router.py`, `data/models.py`, `data/guest_sessions.py`, `alembic/versions/0003_*.py` |
| B, the run path | T-4.10-03, T-4.10-05 | `auth/dependencies.py`, `adapters/web_sse/app.py`, `core/run_registry.py` |
| C, the frontend | T-4.10-08, T-4.10-09 | `frontend/src/**` |
| D, the contract | T-4.10-07 | `contracts/events.py`, its producer, `frontend/src/lib/events.ts` |

C and D both touch `frontend/src/lib/events.ts`. D owns it; C does not write it. Stated here because an unstated overlap is how two builders' branches conflict at integration.

## What is deliberately not in this phase

- Durable run history that survives a reload. Build phase 4.6, and the copy is corrected here rather than left to promise it.
- Per-layer API throttling and the bounded queue per API family. That is what remains of build phase 6.0, untouched by this split.
- Writing `interactions` rows, F-2.0-04. Build phase 4.6.
- Device or IP-level abuse resistance. The clearable-token decision declines it explicitly.
- OAuth, email verification, or any change to the registered auth path beyond accepting an optional guest token.

## Findings

(filed by the judge and adversary rounds)

### F-4.10-01: the sign-in wall promises history that nothing persists

Status: confirmed, at decomposition
Raised by: lead, stage 3

The wall reads "Your history moves with you when you sign in." Nothing persists a run: the `RunRegistry` is in-memory and evicts, and the browser's list is React state. T-4.10-06 corrects the copy and migrates the live runs, which is what actually exists. Durable history is build phase 4.6's.

### F-4.10-02: `snapshot_date` is a graph-snapshot proxy, not a real per-row ingestion date

Status: confirmed, at T-4.10-07's investigation step
Raised by: builder, T-4.10-07

T-4.10-07's own acceptance criterion and F-4.8-D-03's text both describe the SNAPSHOT field as "the date the graph row was ingested." No such field exists: F-3.4-T06-01 (`tracker/phase_3.4.md`, live-confirmed 2026-08-09) already checked `docs/data-engineering/Knowledge_graph_on_server_reference.md` in full and found no ingest-metadata table anywhere this repo can read. What is real and threaded through every Layer 1 row (`cypher_provenance.to_output_row`'s `graph_snapshot_version`) is a Hetzner disk-snapshot label taken around the same time as the graph load, not a dedicated data-ingestion timestamp field, per `synthesis/freshness.py`'s own `graph_snapshot_date_from_version` docstring. `CitationPayload.snapshot_date` is populated from exactly that label (via the same lookup T-3.4-06's staleness check already uses), so it answers "how current is this graph snapshot," a real and useful freshness signal for Section 7's argument, but a reader should not be told it is a genuine per-row ingestion date, since that field does not exist in this graph. Not a blocker: the field is added as specified, with this caveat documented here and in `CitationPayload`'s own docstring. Worth a copy check on the shipped source card (a future ticket, not this one): the UI label should say "snapshot" or "graph snapshot," never "ingested."

### F-4.10-03: an assertion was hollowed out without being edited

Status: confirmed and closed, same session
Raised by: lead, mutation-testing the phase's own frontend work

`phase48Premise.test.tsx`'s clause 3e is the guard against build phase 4.8's worst defect: an anonymous visitor asking any question was shown a fabricated, fully cited answer carrying a real NCBI source URL. This phase preserved every one of that clause's assertions verbatim, and the builder's report said so accurately.

Preserving them was not enough. Clause 3e reaches its assertions through a run whose stream never resolves, so the answer screen never mounts and the absence checks pass without being able to fail. Before this phase the same clause ran with the visitor sitting on the sign-in wall, and the defect it was written against DID render an answer screen, so the checks bit. Making the anonymous path real moved the scenario out from under them.

Measured, not argued. A fabricated cited source was forced into `AnswerScreen`, and clause 3e passed. Two other suites caught the mutation; neither was the anonymous-fabrication guard.

Closed by a new clause in `frontend/src/phase410Premise.test.tsx` that lands the run instead of hanging it, so the answer screen actually mounts. That clause needed two mutation rounds of its own before it was real:

- The first mutation was inert, because sources render inside a `sources.length > 0` guard and injecting into the map could never fire on an empty list. A mutation that cannot fire proves nothing.
- The first version of the new clause was itself vacuous, waiting on a `run-screen` testid that does not exist anywhere in this codebase, so the wait resolved instantly and the absences ran against the run screen. It now waits on `answer-meta`, an element only the answer screen renders, and goes red under the corrected mutation.

Two transferable lessons, both for `LEARNINGS.md`:

- An assertion can be hollowed out without being edited, by changing the state the code reaches before evaluating it. Reviewing a test file's diff cannot detect this; every line looks preserved, because every line is. Only running a mutation can. This repository already counts six assertions that could not fail; this is the first one that became unable to fail while nobody touched it.
- A mutation that does not fire is not evidence of a passing gate, and it reads exactly like one. Before crediting a green result under mutation, confirm the mutation reached the code path at all.

### F-4.10-04: the mint throttle's first version refused the gate's own admit arm

Status: confirmed and closed, same session
Raised by: lead, running the gate after building design decision 8's throttle

The per-source mint throttle shipped its first version at 10 mints per minute, and the premise gate's ADMIT arm went red: eleven clauses failed with `guest_mint_throttled` because the whole suite mints from one apparent source. That is not a test artifact. Many legitimate users share one address behind corporate NAT, a university network, or conference wifi, and those are exactly the rooms where an anonymous demo gets shown, so the same value would have refused real visitors.

This is the phase premise happening to the phase's own author. A control with no safe direction of failure needs both arms, the arm that catches "refuses everybody" is the one no attack test will ever provide, and I had just written that sentence at the top of the gate before committing the error underneath it.

Closed by raising the window to 60 per minute and adding `TestMintThrottleHasBothArms`, which asserts both directions: a pathological burst is refused, and 25 mints from one shared address are not. Both mutation-proven. Raising it costs little because this control is not the bound: the system-wide daily ceiling limits spend, and the throttle's only job is to stop the burst that exhausted the connection pool in F-4.10-A-02.

### F-4.10-05: `blocked_reason` is on the wire and the UI does not read it

Status: open
Raised by: lead, building design decision 8

`GET /v1/allowance` now returns `blocked_reason: "anon_daily_cap_reached"` when the system-wide daily ceiling is spent, and the backend is honest about it: constraint 4 of design decision 8 is met at the API. The frontend has the field in its type and does not render it, so the five dots can still show "5 searches left" to a visitor whose next query will be refused 429.

That is the same reporting-versus-enforcement mismatch F-4.10-A-03 was filed for, one level up, and it is stated here rather than left for someone to find. It is narrower than A-03 was: the guest's own numbers are true, the refusal when it comes is a truthful 429 with a real `Retry-After`, and the condition only arises on a day the whole system has hit its anonymous ceiling. It is still a promise the UI cannot keep.

Owner: the next frontend ticket. Small: `App.tsx` already fetches this response and already has a wall to show.

### F-4.10-R-11: the gate proved a bound existed and stayed blind to its value

Status: confirmed and closed, same session
Raised by: lead, mutation-testing the F-4.10-R-01 fix

The attempt ceiling and the shared daily ceiling bound anonymous spend only TOGETHER, and only while the first is materially smaller than the second. Raise `ATTEMPT_ALLOWANCE` above the shipped `ANON_DAILY_RUN_CAP`, or drop that cap near it, and one guest token takes the whole day again, which is the denial of service F-4.10-R-01 measured at 200 pipelines in 1.68 seconds.

Nothing tested that relationship, and the premise gate structurally could not. Its attack clause imports `ATTEMPT_ALLOWANCE` and scales its own daily cap to four times whatever it finds, so it verifies a bound EXISTS while remaining blind to both numbers. Measured: changing the constant from 10 to 40 left all 32 clauses green.

That is the exact trap the premise gate's own header warns about, in the comment above `_EXPECTED_FREE_SEARCHES`: "a gate that reads its expected value out of the code it grades cannot catch that value being wrong." The file states the principle and imports the next constant one screen later. Neither the builder who wrote the clause nor the re-reviewer who ran 11 mutations against this phase caught it, because both were asking whether the mechanism worked.

Closed by a clause over the SHIPPED defaults in `test_cost_control.py`, mutation-proven at the same value 40 that fooled the gate.

Two things worth carrying:

- The first version enforced the ratio inside `anon_daily_run_cap()`, which is stronger in principle: it refuses the misconfiguration rather than testing for it. It turned 7 legitimate tests red, because every clause exercising the daily ceiling sets a deliberately tiny cap to reach the boundary in a few requests. A control that forces the tests exercising a bound to stop exercising it is a bad control however much it catches, so it was reverted for the weaker one. Stated rather than quietly chosen.
- What the shipped-defaults test does NOT catch: an operator setting a bad value in a real `.env`. Closing that needs startup-time config validation this service does not have. Owner: build phase 6.1's hardening pass.

## Carried open, with an owner each

Triaged 2026-08-15 at phase close. Nothing below is unowned, and nothing is left as "someone should look at this", which is the disposition `LEARNINGS.md` records falling through twelve phases.

| Finding | What it is | Owner |
|---------|-----------|-------|
| F-4.10-05 | `blocked_reason` is on the wire and honest; the UI does not read it, so on a day the system hits its anonymous ceiling the dots can still show searches left before a truthful 429. Narrower than the F-4.10-A-03 it descends from: the guest's own numbers are true and the refusal is honest when it comes | The next frontend ticket. Small: `App.tsx` already fetches this response and already has a wall |
| F-4.10-A-09 | A non-UUID `guest_id` inside a validly signed token escapes as an unhandled 500 rather than a handled rejection. Unreachable without the derived signing key, so latent rather than live. The docstring claiming a backstop was corrected; the backstop itself was not added, because where the shape check belongs (the decoder's contract, or the reader's) is a design decision, not a line to slip in under a comment fix | Build phase 6.1's hardening pass, or whichever ticket next touches `decode_guest_token`'s contract |
| F-4.10-A-10 | The concurrent-run cap (5) equals the free allowance (5), so a guest who has spent everything can reach the 429 path and be told to wait for a run to finish, which is untrue advice for them. The two caps meaning different things while sharing a number is also what made the concurrency clause unable to fail (F-4.10-J-02) | The next backend ticket. Changing either constant fixes it; the message needs to branch on which bound was hit |
| F-4.10-A-11 | A guest's lifetime allowance renders as "N of 5 searches left today". Nothing in the guest path has a daily boundary. The word is wrong, not the number | The next frontend ticket, with F-4.10-05. One-line branch on `allowance.kind` |
| F-4.10-A-12 | The allowance refresh after a run is fire-and-forget, so a failed refresh leaves the dots stale in the direction that ends in a refusal rather than the direction that ends in a surprise | The next frontend ticket |
| F-4.10-A-13 | A first-time visitor never sees the five dots at all, because minting is lazy and the footer renders only once an allowance exists. The affordance the design uses to make the offer is invisible until after the offer has been taken | Product owner: whether the dots should appear before the first ask is a design question, not a bug. It interacts with the deliberate choice not to mint on page load |
| F-4.10-A-14 | After migration `RunEntry.user_id` is rewritten but the run's own `Query.user_id` stays `None`. Not reachable today, since nothing reads `Query.user_id` after a run starts. It becomes live the moment build phase 4.6 writes an `interactions` row from a migrated run, which would then be attributed to nobody | Build phase 4.6, and before it writes its first `interactions` row |
| Playwright flakiness | The frontend suite disagreed with itself across three consecutive runs at its 15s timeout under load (F-4.10-R-10). A gate that fails a tenth of its cases under load is a gate that gets ignored | Build phase 6.1, with CI, since CI is where load-dependent flakiness stops being anecdotal |
| `FollowUp.tsx` fallback | `searchLimitLabel ?? "Search limit applies"` is dead today (`App.tsx` always passes a value) and would be false if it ever rendered | The next frontend ticket, with F-4.10-05 |
| `alembic/0004`'s docstring | Says the daily cap is "the only enforced spending bound on an anonymous caller", which stopped being true at revision 0005. Left alone deliberately: a landed migration's prose describes the state at that revision | Nobody. Recorded so the next reader knows it is stale by design rather than by neglect |
