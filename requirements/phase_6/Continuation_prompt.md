# Phase 6 continuation prompt

Phase 6 is the build. Read this file at the start of any session that continues build work.

## Table of contents

- [State now](#state-now)
- [Read before opening 2.2](#read-before-opening-22)
- [Open items](#open-items)
- [Handover](#handover)

## State now

Five build phases are done and merged into `main`:

| Phase | Delivered | PR |
|-------|-----------|-----|
| 1.0 | FastAPI skeleton, the typed event contract, Pydantic boundary validation | #5 |
| 1.1 | Auth service, the PostgreSQL user-data schema | #6 |
| 2.0 | Real LangGraph agent loop, the three-tier harness | #9 |
| 1.2 | React shell, SSE streaming, chat UI wired end to end | #12 |
| 2.1 | cypher_query over Layer 1, first live graph access | #15 |

Current counts, stated once here:

- Python tests: 977
- Frontend tests: 120
- Playwright end-to-end tests: 3
- Premise gate: 9 of 9
- Decisions logged: 188
- Learnings entries: 36, plus a retrospective

Next phase is 2.2, branch `phase/2.2-write-step-grounding`, depends on 2.1. Per `requirements/Technical_specification.md` Section 25, it delivers: "Deterministic cite-or-refuse, the provenance type wired for Layer 1 citations, a first version of the trust signal for the graph-only path, the two required tests from Section 23."

Per-phase detail lives in `tracker/phase_N.M.md`. Phase narrative lives in `requirements/Plan.md`'s Revision history. Status and open flags live in `tracker/BOARD.md`. This file points at those, it does not copy them.

## Read before opening 2.2

In this order:

1. `LEARNINGS.md`'s build phase 2.1 retrospective, "why build phase 2.1 took five review rounds". The shortest useful account of how a phase passes every ticket and still does not work.
2. `docs/build/Build_workflow_cadence.md` stage 5, the blocking premise gate. It applies to 2.2, since cite-or-refuse over model-generated synthesis is itself a model-generated deliverable.
3. `tracker/phase_2.1.md`'s close-status section, including its deferred findings.
4. `requirements/Technical_specification.md` Section 25, for the build order.

## Open items

One decision below is still waiting on the product owner: whether `security/` stays gitignored. Still ignored today (`.gitignore:50`). This decides whether the Step 6.2 scan results are ever committed.

| Item | Description | Owner |
|------|-------------|-------|
| Fresh judge and adversary pass over the 2.1 surface | The rework was never independently re-reviewed as a whole; findings F-2.1-J4-01, J4-05, J4-06 and B07 sit at in progress, report evidence, do not close | 2.2 |
| F-2.1-C15, generation half | Nothing yet stops generation from producing an unbounded traversal in the first place | 2.2 |
| F-2.1-C07, fourth status value | "Matched plenty, cited none" needs an event-contract change, additive within v1 | 2.2 |
| F-2.1-A5-05 | `mentioned_in` from BRCA1 costs 27 seconds forward plus the full budget reversed, despite being indexed, anchored, and LIMIT 25. Described, deliberately not reproduced | 2.2 |
| F-2.1-A5-02, consumer half | Rows carry a `vocabulary_artifact_fields` marker that nothing reads, since no synthesis prompt exists yet | 2.2 |
| F-06 | 2 of 6 model calls per query bypass the stable prompt prefix, a cost inefficiency, not a correctness defect | 2.2 |
| Vocabulary-artifact rule | Would be strictly better as a name frequency table than its current form | 2.2 |
| Premise-gate coverage statement | Every gate from 2.2 onward must state which question shapes it exercises and which it omits, per `goal-contracts` | 2.2 |
| F-2.1-J4-02, prompt injection | Mitigated by delimiting the question, not closed. `xfail(strict=False)`, clearing the marker is part of 3.0's Guardrail definition of done | 3.0 |
| F-2.1-07 | Gene symbol resolution beyond a one-entry seed table, needs the Layer 2 NCBI lookup | 3.1 |
| F-2.1-B10 | Same cause as F-2.1-07; an unresolvable symbol errors rather than refuses | 3.1 |
| PubTator3 relations endpoint | Path and fields not yet live-verified | 3.3 |
| F-1.2-01 | The run registry never evicts a completed or abandoned run | 4.0 |
| F-1.2-02 | An abandoned client SSE connection does not halt the server-side task | 4.0 |
| F-1.2-03 | The per-run event queue is single-consumer | 4.0 |
| F-2.0-04 | Nothing writes `interactions` rows, so both daily cost caps read zero | 4.6 |
| F-2.0-10 | `trace_id` is client-supplied and never server-overwritten | 4.6 |
| Golden fixture domain sign-off | Nobody is named to verify the clinical and human-variation expected answers | 5.1 |
| F-1.2-04 | Signup's 409 response undermines login's anti-enumeration guarantee. Pair with F-1.1-10, same defect class in the same endpoint | 6.1 |
| Python lockfile | Every backend dependency floats on `>=`, including security-critical ones | 6.1 |
| Stand up CI | No `.github/workflows/` exists; every gate every phase has passed was run by hand | 6.1 |
| Fix `pip install .` | Fails outright on a `package-dir` mapping error, pre-existing | 6.1 |
| Whole-repository security scan | No build-phase code has ever been scanned. One scan predates phase 1.0 | Step 6.2 |
| F-2.1-02 | Section 6.1 documents a parameter mechanism that cannot work; the same wrong claim also sits in `docs/ncbi/Tool_implementation_mechanics.md` and `.claude/rules/production-examples.md` | Step 6.2 |
| F-2.1-01 | The spec says 10 concept labels, the live graph has 11 (the eleventh is `NamedThing`) | Step 6.2 |
| F-2.1-16 | `budget_for_step` diverges from Section 19.1's per-query-class shape, approved but unreconciled | Step 6.2 |
| Env var name divergence | Section 24 names `PER_USER_DAILY_CAP_USD`; the code uses `PER_USER_DAILY_QUERY_CAP`, since it holds a query count, not dollars | Step 6.2 |

Unowned, needing an explicit decision rather than an assumed phase:

- F-1.1-10, F-1.1-11's `User-Agent` half, and F-1.1-18: deferred from build phase 1.1 to 1.2, and 1.2's own ticket list never touched any of the three.
- Auth-path logging: RFC 6819 family revocation still fires silently. Scheduled for build phase 1.2, did not happen, needs a new home.

## Handover

If a different agent takes over, read the "Running this project with a different agent" section in `CLAUDE.md`, which `AGENTS.md` mirrors. Short version: the file artifacts and the model tiering port cleanly, skills and rules port as content but not as invocation, and the four security hooks do not port at all. They are the only structural enforcement in this repo, so substituting them is the first handover step.

Last updated: 2026-08-02.
