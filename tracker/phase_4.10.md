# Build phase 4.10: the anonymous run path and the guest allowance

Branch: `phase/4.10-guest-allowance`
Depends on: 1.1 (merged, PR #6), 4.0 (merged, PR #39)
Opened: 2026-08-15
Status: OPEN. Decomposed, premise gate written and WATCHED FAILING, 16 of 17 red. Builders not yet dispatched.

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
