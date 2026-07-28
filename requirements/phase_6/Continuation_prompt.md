# Phase 6 continuation prompt

Phase 6 is the build. It is underway. Build phase 1.0 (the FastAPI skeleton and typed event contract) and build phase 1.1 (the auth service and the PostgreSQL user-data schema) are both done, judge-reviewed, adversary-tested, and merged into `main` as PR #5 and PR #6. Build phase 2.0 (the LangGraph agent loop) is the recommended next, with 1.2 (the React shell) also unblocked.

This is the file to open at the start of the next build session.

## Table of contents

- [Paste this into a new chat](#paste-this-into-a-new-chat)
- [What Phase 6 is](#what-phase-6-is)
- [Build phase 1.0, done (2026-07-27)](#build-phase-10-done-2026-07-27)
- [Build phase 1.1, done (2026-07-28)](#build-phase-11-done-2026-07-28)
- [Build phase 2.0, what it delivers](#build-phase-20-what-it-delivers)
- [Build phase 1.2, also unblocked](#build-phase-12-also-unblocked)
- [Open items to resolve during Phase 6](#open-items-to-resolve-during-phase-6)
- [If a different agent takes over](#if-a-different-agent-takes-over)

## Paste this into a new chat

---

Phases 1 through 5 of System 3 are complete and merged. Phase 6 (build) is underway; build phases 1.0 and 1.1 are done and merged. Read these before doing anything:

1. `LEARNINGS.md` at the repo root. Read this first, not last. 14 entries now. Two matter most for any phase from here on. The venv-identity entry contains a corrected root-cause diagnosis, so read the correction rather than the original wrong one. The judge-and-adversary entry from phase 1.1 is the one that changes how you write tickets: a scripted gate answers whether the implemented behavior works, an unscripted adversary answers whether that behavior delivers the property the spec claims, and the first cannot reach the second.
2. `requirements/Technical_specification.md` Section 25. The build order: 26 numbered phases, each with its branch name, what it delivers, and what it depends on. This is the source of truth for what gets built and in what sequence. Do not work from a summary.
3. `requirements/phase_5/Coverage_map.md`. The gate list: 303 obligations from the three locked documents, each mapped to the rule or skill that enforces it.
4. `docs/build/Build_workflow_cadence.md`. How a phase runs: eleven stages, who acts at each, the capability tier and effort rung per stage.
5. `tracker/BOARD.md`. Current state: phases 1.0 and 1.1 are `done`, everything else `todo`. Four open flags. The one that binds every remaining prototype phase is the whole-repository security scan, which has never run against any build-phase code.
6. `tracker/phase_1.1.md`. The full record of what phase 1.1 built, including 18 findings with their dispositions. Read this before opening any phase that touches auth, the user-data database, or a security property stated in the spec.
7. `requirements/PRD.md` and `requirements/Evaluation_playbook.md` as needed. The PRD is locked. The playbook is living.

Then start the next build phase:

```
/task-tracker --open 2.0
```

That operation will make you read the phase's Section 25 row, verify its dependencies are merged, read the learnings filtered to this phase, and decompose it into tickets before anyone builds.

Rules that bind here:
- The PRD, tech spec, and strategic memo are frozen. They are edited only at the Step 6.2 reconciliation, not before.
- Build phases get a branch and a pull request. Branch name comes from Section 25.
- Every ticket carries a refinement label. Work does not start until it is `refined`.
- Acceptance criteria are testable statements of a finished condition, never tasks. Phase 1.1 added a sharper version of this rule: when the spec states a security property in words, write the criterion as that property, not as the mechanism meant to produce it. "Replaying a used refresh token returns 401" is a mechanism and it passed while the property failed; "a stolen refresh token cannot be used more than once" is the property and it would have caught the defect.
- Log every decision to `DECISIONS.md`, append only, never modify an existing row.
- Write to `LEARNINGS.md` the moment something breaks, including what did not work. Not at phase end.
- The product owner approves each pull request. Do not start the next phase without it.

---

## What Phase 6 is

Three steps, from `requirements/Plan.md`:

| Step | What it is | Which build phases |
|------|-----------|--------------------|
| 6.1 | The prototype. One real query end to end, through the agent loop, with a real cited answer | 1.0 through 2.2 |
| 6.2 | The one reconciliation pause. Update the PRD, tech spec, and memo from what the prototype taught, sweep the parked new-intake folder, and run the whole-repository security scan | none, a pause |
| 6.3 | Build v1 | 3.0 onward |

## Build phase 1.0, done (2026-07-27)

Delivered: the FastAPI app skeleton, the health endpoint, the Pydantic event contract (`Query`, `RequestContext`, the `Event` envelope, all eleven Section 2.3 payload types), and a typed `run()` stub wired to a query endpoint. 191 tests passing. Judge rejected once (an open-dict payload not bound to its declared type, an unbounded `session_memory` field), both fixed and independently re-verified. Merged as PR #5. Full detail in `tracker/phase_1.0.md`.

## Build phase 1.1, done (2026-07-28)

Delivered, per Section 25 row 1.1 and Section 15:

- Auth primitives: argon2id password hashing, HS256 access tokens with the algorithm pinned explicitly, opaque refresh tokens stored only as SHA-256 hashes.
- Five endpoints at `/auth`: signup, login, refresh, logout, me.
- All six Section 15 tables (`users`, `auth_sessions`, `sessions`, `interactions`, `cq_candidates`, `saved_queries`) as SQLAlchemy models, with two Alembic migrations that both have working downgrades.
- Token lifetimes: 15-minute access, 30-day sliding refresh, 90-day absolute ceiling that does not renew on rotation.
- 314 tests passing, up from 191. Merged as PR #6.

Closed the ecdsa CVE that phase 1.0 accepted as a known risk. `python-jose[cryptography]` was replaced with `PyJWT`, because `ecdsa` is a core requirement of `python-jose` rather than an extra, so it could not be excluded in place. `pip show ecdsa` now reports not found.

Two defects worth carrying forward as cautionary detail, both found by the adversary after the judge had passed the phase:

- The migration test destroyed every row in the developer's real database on each run, while restoring the schema on teardown so nothing looked wrong.
- Refresh rotation shipped correctly but delivered none of the property Section 15 claims for it. Fixed with RFC 6819 reuse detection.

Full detail, including all 18 findings and their dispositions, in `tracker/phase_1.1.md`.

## Build phase 2.0, what it delivers

From Section 25: the LangGraph graph implementing Guardrail, Think, Plan, Act, and Write with stub nodes; the three-tier harness wired to LiteLLM and OpenRouter (Decision C); the coordinator-worker split scaffold; and cost caps plus the cost event enforced from day one. Depends on 1.0 (done). Branch `phase/2.0-langgraph-agent-loop`.

Two rules bind this phase specifically. `prompt-cache-discipline` governs the stable prefix the three-tier harness depends on, and it must be read before the harness code is written, not after. `system-design-patterns` pattern 11 requires that `resolve_model()` never hardcodes a model id: model identity resolves only from environment-configured tier values.

One finding is already queued against this phase from 1.1: F-1.1-17, `/query` is unauthenticated and trusts a client-supplied `user_id`. Phase 2.0 owns server-deriving that value.

## Build phase 1.2, also unblocked

From Section 25: the React shell, SSE consumption of the event stream, an empty chat endpoint wired end to end, and the stop button. Depends on 1.0 (done). Branch `phase/1.2-react-shell-sse`.

It carries two blockers that 2.0 does not. It is marked `product_refine`, so the product owner has a question to settle before work starts, and the board does not record what that question is. Playwright is not installed and must clear `supply-chain-security` before it can be. Three findings from phase 1.1 are queued against it: F-1.1-10 (signup enumeration oracle), F-1.1-11 (a NUL byte in `User-Agent` returns an unhandled 500), and F-1.1-18 (five non-canonical UUID spellings accepted in the `user_id` claim), plus auth-path logging and the `/health` endpoint returning 200 while the database is unreachable.

## Open items to resolve during Phase 6

| Item | Needed before | Owner |
|------|---------------|-------|
| Run the whole-repository security scan. No build-phase code has ever been scanned; the only run in `security/` predates phase 1.0. Scope is the entire repository, not a commit range, so there is no baseline to carry forward | The Step 6.2 reconciliation, and it is a hard prerequisite for starting Step 6.3 | Lead, with product-owner-committed token budget |
| Name a domain sign-off owner for the clinical and human-variation golden fixtures | Build phase 5.1 | Product owner |
| Install Playwright and wire it as the UI gate. Re-verify the version at install time | Build phase 1.2 | Lead |
| Settle the `product_refine` question on build phase 1.2. The board records that one exists but not what it is | Build phase 1.2 opens | Product owner |
| Decide whether unattended overnight runs are wanted | Whenever it becomes obvious | Product owner |
| Live-verify the PubTator3 relations endpoint path and fields | Build phase 3.3 ships | Lead |
| Add auth-path logging. The RFC 6819 family revocation currently fires silently, so the one security event most worth alerting on leaves no record | Build phase 1.2 | Lead |
| Add a lockfile. Every dependency floats on `>=`, including the two security-critical ones added in 1.1 | Build phase 6.1 | Lead |
| Stand up CI. There is no `.github/workflows/`, so every gate every phase has passed was run by hand | Build phase 6.1 | Lead |
| Fix `pip install .`, which fails outright on a `package-dir` mapping error. Pre-existing, not introduced by 1.0 or 1.1 | Build phase 6.1 | Lead |

## If a different agent takes over

Read the "Running this project with a different agent" section in `CLAUDE.md`, which `AGENTS.md` mirrors. The short version: the file artifacts and the model tiering port cleanly, the skills and rules port as content but not as invocation, and the four security hooks do not port at all. They are the only structural enforcement in this repo, so substituting them is the first handover step.
