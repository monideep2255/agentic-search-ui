# Phase 6 continuation prompt

Phase 6 is the build. It is underway: build phase 1.0 (the FastAPI skeleton and typed event contract) is done, judge-reviewed, independently sign-off-verified, and merged into `main` (PR #5, 2026-07-27). Build phase 1.1 (auth service) is next.

This is the file to open at the start of the next build session.

## Paste this into a new chat

---

Phases 1 through 5 of System 3 are complete and merged. Phase 6 (build) is underway; build phase 1.0 is done and merged. Read these before doing anything:

1. `LEARNINGS.md` at the repo root. Read this first, not last. 11 entries now, and they are the mistakes not worth repeating, including a wrong root-cause diagnosis that was later corrected in place: read the correction too, not just the original entry.
2. `requirements/Technical_specification.md` Section 25. The build order: 26 numbered phases, each with its branch name, what it delivers, and what it depends on. This is the source of truth for what gets built and in what sequence. Do not work from a summary.
3. `requirements/phase_5/Coverage_map.md`. The gate list: 303 obligations from the three locked documents, each mapped to the rule or skill that enforces it. This is what the build is measured against.
4. `docs/build/Build_workflow_cadence.md`. How a phase runs: eleven stages, who acts at each, the capability tier and effort rung per stage.
5. `tracker/BOARD.md`. Current state: phase 1.0 is `done`. Phase 1.1 carries a flag, `ecdsa CVE` (accepted risk from phase 1.0's release gate, needs resolving when auth implements JWT signing; see DECISIONS.md 2026-07-27). Phase 1.2 is `product_refine` pending Playwright install. Everything else is `todo`.
6. `tracker/phase_1.0.md`. The full record of what phase 1.0 actually built, including the judge's rejection-and-fix round and the independent sign-off verification. Read this before opening 1.1, since 1.1 depends on 1.0's contracts module.
7. `requirements/PRD.md` and `requirements/Evaluation_playbook.md` as needed. The PRD is locked. The playbook is living.

Then start build phase 1.1:

```
/task-tracker --open 1.1
```

That operation will make you read the phase's Section 25 row, verify its dependencies are merged (1.0 is done, so this passes), read the learnings filtered to this phase, and decompose it into tickets before anyone builds.

Rules that bind here:
- The PRD, tech spec, and strategic memo are frozen. They are edited only at the Step 6.2 reconciliation, not before.
- Build phases get a branch and a pull request. That is required now, unlike the planning phases. Branch name comes from Section 25.
- Every ticket carries a refinement label. Work does not start until it is `refined`. The renderer enforces this and will refuse to build the board if a phase is in progress while unrefined.
- Acceptance criteria are testable statements of a finished condition, never tasks. "cypher_query returns a timeout error after 30 seconds", not "add a timeout".
- Log every decision to `DECISIONS.md`, append only, never modify an existing row.
- Write to `LEARNINGS.md` the moment something breaks, including what did not work. Not at phase end.
- The product owner approves each pull request. Do not start the next phase without it.

---

## What Phase 6 is

Three steps, from `requirements/Plan.md`:

| Step | What it is | Which build phases |
|------|-----------|--------------------|
| 6.1 | The prototype. One real query end to end, through the agent loop, with a real cited answer | 1.0 through 2.2 |
| 6.2 | The one reconciliation pause. Update the PRD, tech spec, and memo from what the prototype taught, and sweep the parked new-intake folder | none, a pause |
| 6.3 | Build v1 | 3.0 onward |

## Build phase 1.0, done (2026-07-27)

Delivered: the FastAPI app skeleton, the health endpoint, the Pydantic event contract (`Query`, `RequestContext`, the `Event` envelope, all eleven Section 2.3 payload types), and a typed `run()` stub wired to a query endpoint. 191 tests passing. Judge rejected once (an open-dict payload not bound to its declared type, an unbounded `session_memory` field), both fixed and independently re-verified. Merged as PR #5. Full detail in `tracker/phase_1.0.md`.

## Build phase 1.1, what it delivers

From Section 25: minimal v1 auth (Step 1.7) and the PostgreSQL user-data schema stood up now (`interactions`, `cq_candidates`, `users`), even though the feedback loop does not populate it meaningfully until phase 4.6. Depends on 1.0 (done). Branch `phase/1.1-auth-service`.

Carries forward from phase 1.0's release gate: `ecdsa` 0.19.2's known CVE (PYSEC-2026-1325, no upstream fix) was accepted as a risk rather than resolved, specifically deferred to this phase since it is pulled in by `python-jose[cryptography]` for JWT signing. Resolve it here, before or as part of implementing that signing, not by silently inheriting it further. See DECISIONS.md 2026-07-27 for the full reasoning.

## Open items to resolve during Phase 6

| Item | Needed before | Owner |
|------|---------------|-------|
| Name a domain sign-off owner for the clinical and human-variation golden fixtures | Build phase 5.1 | Product owner |
| Install Playwright and wire it as the UI gate. Precheck is clean, no postinstall script. Re-verify the version at install time | Build phase 1.2 | Lead |
| Decide whether unattended overnight runs are wanted | Whenever it becomes obvious | Product owner |
| Live-verify the PubTator3 relations endpoint path and fields | Build phase 3.3 ships | Lead |
| Resolve `ecdsa`'s known CVE (accept a mitigation, swap the JWT library, or otherwise) before or as part of implementing JWT signing | Build phase 1.1 | Lead |

## If a different agent takes over

Read the "Running this project with a different agent" section in `CLAUDE.md`, which `AGENTS.md` mirrors. The short version: the file artifacts and the model tiering port cleanly, the skills and rules port as content but not as invocation, and the four security hooks do not port at all. They are the only structural enforcement in this repo, so substituting them is the first handover step.
