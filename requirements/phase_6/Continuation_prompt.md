# Phase 6 continuation prompt

Phase 6 is the build. It is underway. Build phases 1.0 (FastAPI skeleton and typed event contract), 1.1 (auth service and PostgreSQL user-data schema), 2.0 (LangGraph agent loop and the three-tier harness), and 1.2 (React shell and SSE) are all done, judge-reviewed, adversary-tested, and merged into `main` as PR #5, #6, #9, and #12.

Build phase 2.1 (`cypher_query` over Layer 1) is PR #13, built but NOT closed. Its tickets stay `in-review` and its branch is not deleted, because the judge and adversary both failed it pre-rework and none of the rework was independently reviewed. 798 Python tests passing, 23 learnings recorded, 174 decisions logged. Next up is build phase 2.2, whose first task is a fresh judge and adversary pass over the 2.1 surface, not new code. Read the "Build phase 2.1, done with one recorded gap" section below and `tracker/phase_2.1.md`'s "Phase close status" before opening anything.

This is the file to open at the start of the next build session.

One decision is still waiting on the product owner. It is in the open items table below, with the reasoning behind it. Do not assume it.

- Whether `security/` stays gitignored, which decides whether the Step 6.2 scan results are ever committed. Still ignored today (`.gitignore:50`).

## Table of contents

- [Paste this into a new chat](#paste-this-into-a-new-chat)
- [What Phase 6 is](#what-phase-6-is)
- [Build phase 1.0, done (2026-07-27)](#build-phase-10-done-2026-07-27)
- [Build phase 1.1, done (2026-07-28)](#build-phase-11-done-2026-07-28)
- [Build phase 2.0, done (2026-07-28)](#build-phase-20-done-2026-07-28)
- [Build phase 1.2, done (2026-07-28)](#build-phase-12-done-2026-07-28)
- [Build phase 2.1, what it delivers, next up](#build-phase-21-what-it-delivers-next-up)
- [Open items to resolve during Phase 6](#open-items-to-resolve-during-phase-6)
- [If a different agent takes over](#if-a-different-agent-takes-over)

## Paste this into a new chat

---

Phases 1 through 5 of System 3 are complete and merged. Phase 6 (build) is underway; build phases 1.0, 1.1, 2.0, and 1.2 are done and merged. Read these before doing anything:

1. `LEARNINGS.md` at the repo root. Read this first, not last. 19 entries now. Three matter most for any phase from here on, beyond the venv-identity and judge-and-adversary entries already flagged in earlier versions of this file. The `ChatPage` wiring row (build phase 1.2): a leaf-level ticket can satisfy its own acceptance criteria while the phase's actual end-to-end deliverable goes unwired, unless one ticket explicitly owns the assembly. The run-lifecycle row (build phase 1.2, adversary pass): a green scripted judge review carries no signal on resource lifecycle when no acceptance criterion named it, so a judge pass and an adversary pass are not redundant even back to back on the same phase. The tracker-backfill row implicit in T-1.2-01 through 04's own History sections: evidence not filled in at build time has to be reconstructed later from a judge's independent re-verification, which is real but avoidable cost.
2. `requirements/Technical_specification.md` Section 25. The build order: 26 numbered phases, each with its branch name, what it delivers, and what it depends on. This is the source of truth for what gets built and in what sequence. Do not work from a summary.
3. `requirements/phase_5/Coverage_map.md`. The gate list: 303 obligations from the three locked documents, each mapped to the rule or skill that enforces it.
4. `docs/build/Build_workflow_cadence.md`. How a phase runs: eleven stages, who acts at each, the capability tier and effort rung per stage.
5. `tracker/BOARD.md`. Current state: phases 1.0, 1.1, 1.2, and 2.0 are `done`, everything else `todo`. Eleven open flags, four of them new from build phase 1.2's adversary pass (F-1.2-01 through F-1.2-04). The scan flag still binds every remaining prototype phase: the whole-repository security scan has never run against any build-phase code.
6. `tracker/phase_1.1.md` and `tracker/phase_1.2.md`. The full record of what each phase built. Read `phase_1.1.md` before opening any phase that touches auth, the user-data database, or a security property stated in the spec. Read `phase_1.2.md` before opening build phase 2.1, since its own T-1.2-08 entry is the concrete, worked example of the ticket-boundary integration gap named in the `LEARNINGS.md` row above, and because three findings deferred from phase 1.1 (F-1.1-10, F-1.1-11, F-1.1-18) were scheduled to close in phase 1.2 and did not; they carry forward, unresolved, see the open items table below.
7. `requirements/PRD.md` and `requirements/Evaluation_playbook.md` as needed. The PRD is locked. The playbook is living.

Build phase 2.1 (`cypher_query` over Layer 1) is next by dependency: it depends only on 2.0, which is done, and it is the phase every remaining tool-integration and citation-grounding phase sits behind. Its refinement label is `tech_refine`, not yet `refined`, so opening it is what turns the Section 25 row into scoped tickets:

```text
/task-tracker --open 2.2
```

Before any of 2.2's own tickets, its first task is a fresh judge and adversary pass over the build phase 2.1 surface. 2.1 merged without independent review of its rework, and 2.2 builds directly on that code.

That operation will make you read the phase's Section 25 row, verify its dependencies are merged, read the learnings filtered to this phase, and decompose it into tickets before anyone builds. Confirm with the product owner before opening if anything about scope feels underspecified; the phase's own Flags column already names two findings (F-2.0-08, F-2.0-14) that become live the moment this phase's real tool calls exist, and those need a ticket, not a surprise.

Rules that bind here:
- The PRD, tech spec, and strategic memo are frozen. They are edited only at the Step 6.2 reconciliation, not before.
- Build phases get a branch and a pull request. Branch name comes from Section 25.
- Every ticket carries a refinement label. Work does not start until it is `refined`.
- Acceptance criteria are testable statements of a finished condition, never tasks. Phase 1.1 added a sharper version of this rule: when the spec states a security property in words, write the criterion as that property, not as the mechanism meant to produce it. Phase 1.2 added another: when a phase's own Section 25 line names an end-to-end deliverable ("wired end to end"), at least one ticket must have that exact deliverable as its acceptance criterion, or the phase can pass every ticket and still not deliver what it promised.
- Log every decision to `DECISIONS.md`, append only, never modify an existing row. 165 rows as of build phase 1.2 close.
- Write to `LEARNINGS.md` the moment something breaks, including what did not work. Not at phase end.
- Never resume the same judge agent to re-verify or close its own findings. Route re-verification to a fresh-context agent, per the phase 1.0 `LEARNINGS.md` row on this and per build phase 1.2's own close, which used a fresh confirmation pass rather than resuming the original judge.
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

Three findings were deferred to build phase 1.2 rather than fixed here: F-1.1-10 (signup enumeration oracle), F-1.1-11 (a NUL byte in `User-Agent` returns an unhandled 500, the `email` half already closed as a side effect of a different fix), and F-1.1-18 (five non-canonical UUID spellings accepted in the `user_id` claim). Build phase 1.2's own ticket list never touched any of the three; they remain open, see the open items table below.

Full detail, including all 18 findings and their dispositions, in `tracker/phase_1.1.md`.

## Build phase 2.0, done (2026-07-28)

Delivered, per Section 25 row 2.0: the real five-node LangGraph Guardrail, Think, Plan, Act, Write loop, replacing the phase 1.0 stub; the three-tier harness wired to LiteLLM and OpenRouter with per-model cost accounting; all four Section 19.1 cost caps enforced (the per-query cap and per-step timeouts live end to end, the two daily caps are wired but read zero until phase 4.6 writes `interactions` rows); the coordinator-worker split scaffold; the prompt-cache stable-prefix scaffold. Integrated into a real `run()` callable proven end to end against the authenticated `/query` endpoint with LiteLLM mocked.

Judge-reviewed (all 8 tickets passed, phase-level premise independently verified) and adversary-tested (8 findings filed, all confirmed by a second judge triage; 4 fixed in-phase, 4 deferred with named triggers tracked on `tracker/BOARD.md` against build phases 2.1, 4.6, and 7.0). A ninth, judge-filed finding (F-2.0-05, whether the final cost figure may reach an end-user surface) was resolved by explicit product-owner decision: cost and token usage are internal-only, never shown to the end user. 483 tests passing, up from 314. Merged as PR #9.

Two of the eight tickets have findings that become live only once a later phase gives them real inputs to act on, so they carry forward rather than close outright:

- F-2.0-08: the Act step's coordinator-worker reader calls bypass the per-query cost cap and the per-step timeout entirely. Latent today, since `plan`'s stub always produces an empty `tool_calls` list. Trigger: build phase 2.1, wired in alongside `act_node`'s first real tool call.
- F-2.0-14: the coordinator-worker structured pass-through path applies no `maxLength`/`maxItems`, the default branch every tool adapter hits unless it opts into the reader. Trigger: build phase 2.1, before the first tool adapter returns real API JSON.

Full detail in `tracker/phase_2.0.md`.

## Build phase 1.2, done (2026-07-28)

Delivered, per Section 25 row 1.2: the React shell, SSE consumption of the event stream, an empty chat endpoint wired end to end, and the stop button. Depended on 1.0. Branch `phase/1.2-react-shell-sse`. All 8 tickets done (T-1.2-01 through T-1.2-08, the last added mid-phase).

- Incremental streaming: `core/run_streaming()` drives `compiled_graph.astream(stream_mode="updates")`; `core/run_registry.py` (new) tracks in-process runs.
- Three new endpoints alongside the untouched buffered `POST /query`: `POST /v1/query` (202, mints `run_id`), `GET /v1/query/{run_id}/events` (SSE), `POST /v1/query/{run_id}/stop` (idempotent).
- `frontend/` (new top-level directory): Vite plus React 19 plus TypeScript. `useAgentRun` consumes SSE via `fetch()` and a hand-parsed `ReadableStream`, not native `EventSource`, since this backend authenticates with a Bearer token and `EventSource` cannot set custom headers.
- The full chat UI (`QueryPipelineStepper`, `AnswerStream`, `GuardrailBanner`, `CapMessage`, `LoadingSkeleton`, `StopButton`) and, added mid-phase as T-1.2-08 to close a gap where the components existed and were unit-tested but nothing assembled them, `AuthGate` (real login and signup against the phase 1.1 backend, token held in memory only) wiring `ChatPage` end to end.
- Playwright installed (`@playwright/test` 1.62.0, `@axe-core/playwright` 4.12.1, both pinned exact after a live supply-chain re-verification) with three real end-to-end tests: the full query flow, a mid-stream stop proven to halt the server-side task, and a WCAG-scoped axe-core accessibility scan.

Judge-reviewed (all 8 tickets passed on the code; the review also caught that 4 tickets' tracker records were never backfilled at build time and a dead-code defect in `ChatShell.tsx`, both fixed) and adversary-tested against the real running system (6 findings: 1 fixed in-phase, an unvalidated empty or whitespace-only query burning a full pipeline run; 4 deferred with named triggers on `tracker/BOARD.md`; 1 rejected as spec-conformant behavior). 539 Python tests passing, up from 483, plus 120 frontend unit tests and 3 Playwright end-to-end tests. Merged as PR #12.

Four findings carry forward as open flags, none blocking this phase's own close:

- F-1.2-01, F-1.2-02, F-1.2-03: the run registry never evicts a completed run, an abandoned client connection does not halt the server-side task, and the per-run event queue is single-consumer so a second listener gets nothing. All three deferred to build phase 4.0 ("the REST plus SSE adapter finalized as the public API surface").
- F-1.2-04: signup's `409` response undermines login's own verified anti-enumeration guarantee. Deferred to build phase 6.1's hardening pass or an earlier product decision. This is closely related to F-1.1-10 (the signup enumeration oracle deferred from phase 1.1 and still open, see above); whichever phase finally fixes signup enumeration should treat the two as one problem, not two separate tickets.

Full detail, including all 8 tickets' evidence and all 6 adversary findings, in `tracker/phase_1.2.md`.

## Build phase 2.1, what it delivers, next up

From Section 25: `cypher_query` over Layer 1, schema slicing, validate-then-execute generation, edge-label enforcement. Depends on 2.0 (done). Branch `phase/2.1-cypher-tool`. Refinement label is `tech_refine`; opening it with `/task-tracker --open 2.1` is what decomposes it into tickets.

Two findings from phase 2.0 are already queued against this phase, both because they are latent only until real tool calls exist: F-2.0-08 (the coordinator-worker reader bypasses the per-query cost cap and the per-step timeout) and F-2.0-14 (the coordinator-worker pass-through path applies no `maxLength`/`maxItems`). Both need a ticket in this phase's own decomposition, not a follow-up filed after the fact.

`docs/ncbi/Tool_implementation_mechanics.md` has the per-tool API traps taken from Section 6, including edge-label enforcement for `cypher_query` specifically. Read it before writing the query generation or validation logic.

## Build phase 2.1, done with one recorded gap (2026-07-29)

Delivered, per Section 25 row 2.1: `cypher_query` over Layer 1 through an SSH tunnel, schema slicing, the validate-then-execute generation pipeline with one repair retry, and edge-label enforcement. 798 Python tests passing. Branch `phase/2.1-cypher-tool`.

Read the "Phase close status" section at the top of `tracker/phase_2.1.md` before opening build phase 2.2. The short version, and it is the one thing a reader would otherwise get wrong:

- The phase premise is met. `tests/system_03_search_agent/tools/test_cypher_query_e2e.py` runs 9 tests against the live 115M-node graph with only the model call mocked, and all 9 pass. That gate cannot be satisfied by mocks, which is exactly what exposed the original failure.
- The judge and the adversary both FAILED this phase on the pre-rework code, filing roughly 27 findings including 2 critical and 5 high. Every blocker was then fixed. None of that rework has been reviewed by any independent agent.
- This phase produced one false green already: every ticket read green, and the judge still found the premise unmet while the adversary found 17 defects. A green suite has a track record of being wrong here.
- Merged on an explicit product-owner decision against a weekly budget limit, with the gap recorded rather than glossed. A fresh judge and adversary pass over the phase 2.1 surface is build phase 2.2's first task, not an optional extra.

What this phase established that later phases depend on:

- Layer 1 access is an SSH local port-forward, `ssh -N -L 15432:127.0.0.1:5432 root@46.225.128.133`. Postgres binds 127.0.0.1 only, so there is no direct-connect option. Nothing in the repo opens the tunnel, so a fresh clone cannot run the live tests until someone does it by hand.
- The graph credential is `kg_reader`, created 2026-07-29 with product-owner approval: non-superuser, `pg_read_all_data`, `default_transaction_read_only`, 30s `statement_timeout`, and `session_preload_libraries = age`. A non-superuser cannot run `LOAD 'age'`, which is why the preload is set per role.
- The harness could not complete a single real model call before this phase: the fallback price table was empty and none of the three tier defaults is in litellm's price map, so every call was billed by OpenRouter and then discarded. Fixed, with prices read from OpenRouter's own catalogue.
- Per-tier reasoning effort and `max_tokens` ceilings are now set on every `call_tier` call. Reasoning tokens bill as output tokens, so an uncapped reasoning model is an uncapped bill.

Still open after this phase:

- F-06: 2 of 6 model calls per query bypass the stable prompt prefix. Cost inefficiency, not a correctness defect.
- F-2.1-02: `Technical_specification.md` Section 6.1 states a parameter-passing mechanism that cannot work. psycopg2 interpolates `%s` client-side, so AGE never receives a bind parameter and rejects the call. The working form is `PREPARE`/`EXECUTE`. The same claim appears in `docs/ncbi/Tool_implementation_mechanics.md` and in `.claude/rules/production-examples.md` example 1, whose "correct" sample uses the non-working form, so it will mislead every remaining tool build. A Step 6.2 reconciliation item.
- F-2.1-01: the spec says 10 concept labels, the graph has 11. Also Step 6.2.
- The spec's Section 24 env-var table names `PER_USER_DAILY_CAP_USD`, but the code deliberately renamed it to `PER_USER_DAILY_QUERY_CAP` in phase 2.0 because it holds a query count, not dollars. Anyone provisioning from the spec instead of `env.example` reproduces a broken config. Step 6.2.

## Open items to resolve during Phase 6

| Item | Needed before | Owner |
|------|---------------|-------|
| A fresh judge and adversary pass over the build phase 2.1 surface. Both failed the phase pre-rework; none of the rework was independently reviewed. Detail in `tracker/phase_2.1.md`'s "Phase close status" | Build phase 2.2's first task | Lead |
| Run the whole-repository security scan. No build-phase code has ever been scanned; the only run in `security/` predates phase 1.0. Scope is the entire repository, not a commit range, so there is no baseline to carry forward | The Step 6.2 reconciliation, and it is a hard prerequisite for starting Step 6.3 | Lead, with product-owner-committed token budget |
| Decide whether `security/` should stay gitignored (`.gitignore:50`). Nothing under it is tracked, so the Step 6.2 whole-repository scan results would not be committed: not reviewable in a pull request, not diffable against a later scan, and gone on a fresh clone. Cheaper to settle before the scan runs than after | The Step 6.2 scan runs | Product owner |
| Name a domain sign-off owner for the clinical and human-variation golden fixtures | Build phase 5.1 | Product owner |
| F-1.1-10, F-1.1-11 (the `User-Agent` half only), F-1.1-18: three findings deferred from phase 1.1 to phase 1.2 that phase 1.2's own ticket list never touched. Still open, no longer attached to a specific upcoming phase | Before build phase 4.0 or 6.1, whichever picks up the auth-hardening backlog first; needs an explicit owner decision, not an assumption | Lead, product owner to confirm which phase |
| F-1.2-01, F-1.2-02, F-1.2-03: the run registry never evicts, an abandoned client connection does not halt the server-side task, the per-run event queue is single-consumer | Build phase 4.0 | Lead |
| F-1.2-04 and F-1.1-10 together: signup's `409` response and the signup timing/status oracle are the same class of defect in the same endpoint and should be fixed as one ticket, not two | Build phase 6.1's hardening pass, or an earlier explicit product-owner decision if judged urgent before then | Lead, product owner to confirm urgency |
| F-2.0-08, F-2.0-14: bypass the cost cap and timeout, and no `maxLength`/`maxItems`, both latent until real tool calls exist | Build phase 2.1, wired in alongside the first real tool call | Lead |
| F-2.0-04, F-2.0-10: the daily caps read zero because nothing writes `interactions` rows, and `trace_id` is client-supplied and never server-overwritten | Build phase 4.6 | Lead |
| Add auth-path logging. The RFC 6819 family revocation still fires silently (confirmed absent from `src/system_03_search_agent/auth/` as of phase 1.2 close), so the one security event most worth alerting on leaves no record. This was scheduled for build phase 1.2 and did not happen; it needs a new home | Not yet scheduled; needs an explicit next phase | Lead |
| Live-verify the PubTator3 relations endpoint path and fields | Build phase 3.3 ships | Lead |
| Add a lockfile for the Python backend. Every dependency floats on `>=`, including security-critical ones. The frontend already has one (`package-lock.json`, committed since build phase 1.2) | Build phase 6.1 | Lead |
| Stand up CI. There is no `.github/workflows/`, so every gate every phase has passed was run by hand | Build phase 6.1 | Lead |
| Fix `pip install .`, which fails outright on a `package-dir` mapping error. Pre-existing, not introduced by any build phase so far | Build phase 6.1 | Lead |
| Decide whether unattended overnight runs are wanted | Whenever it becomes obvious | Product owner |

## If a different agent takes over

Read the "Running this project with a different agent" section in `CLAUDE.md`, which `AGENTS.md` mirrors. The short version: the file artifacts and the model tiering port cleanly, the skills and rules port as content but not as invocation, and the four security hooks do not port at all. They are the only structural enforcement in this repo, so substituting them is the first handover step.
