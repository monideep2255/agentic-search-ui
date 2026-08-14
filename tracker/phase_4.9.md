# Build phase 4.9: answer-screen and chrome fidelity

Branch: `phase/4.9-answer-screen-fidelity`
Depends on: 4.8 (merged, closed out via PR #42 and PR #43)
Opened: 2026-08-14
Status: OPEN, PAUSED AT THE PREMISE GATE. Gate written and watched failing, 12 of 12. No build code written yet.

Deliverable: close the nine fidelity gaps between the running app and the approved prototype, plus the account menu. Scheduled 2026-08-14 by product-owner decision rather than left as undated flags.

## Table of contents

- [The premise](#the-premise)
- [Where this stopped, and how to resume](#where-this-stopped-and-how-to-resume)
- [Tickets](#tickets)
- [What is deliberately not in this phase](#what-is-deliberately-not-in-this-phase)
- [How these were found](#how-these-were-found)

## The premise

> The run and answer screens present what the approved prototype presents, in the prototype's own order, with the specifics the prototype names rather than summaries of them.

Source of truth: `docs/build/design/design-system/prototype/app.html`, `#s-answer` and its `finish()` renderer. The prototype's order is askline, `.summary` (verdict, meta, Show work), the spine and answer grid, then `#tail`: sources, verdict pills, follow-up, feedback.

The gate is `frontend/src/phase49Premise.test.tsx`. Its own coverage statement names what it does not test, including the two fields the backend cannot supply.

## Where this stopped, and how to resume

Paused at the product owner's request, at a deliberate boundary: the premise gate is written and watched failing, and NOT ONE LINE of build code exists yet. That is stage 5 of `docs/build/Build_workflow_cadence.md`, and it is the cleanest place in the cadence to stop.

State, verified rather than assumed:

| Check | Result |
|-------|--------|
| Working tree | Clean. Only `phase49Premise.test.tsx` is new; `git diff develop` is empty for every other file |
| Pre-existing suite | 134 passed, 10 files, unchanged from `develop` |
| Full suite | 146 tests, 12 failed, 134 passed. THE 12 FAILURES ARE THIS GATE AND ARE EXPECTED |
| Typecheck | Clean |
| Stability | Three consecutive full runs at exactly 12 failed / 134 passed |

One consequence worth knowing before it is mistaken for a clean check: `tracker/check_doc_drift.py` SKIPS the frontend test-count facts while the suite is red, because it parses vitest's "Tests N passed" line and a failing run does not print one. It reports `ok ... (2 skipped)` rather than failing. So during any phase's gate-first stage, the test counts are unverified rather than verified. `develop`'s counts are correct and untouched; nothing here needs updating until this phase goes green.

`npx vitest run` is RED on this branch, by design. A green run here would mean the gate cannot fail, which is the defect this repository has hit nine times.

Resume by working the tickets below in order. Ticket T-4.9-01 is the one everything else waits on, because three separate clauses need data the view does not currently carry.

## Tickets

| Id | Deliverable | Finding | Depends on | Status |
|----|-------------|---------|------------|--------|
| T-4.9-00 | The premise gate, written first and watched failing | | none | done |
| T-4.9-01 | `useRunView` carries the run's elapsed time, its step narratives with timings, the distinct layer count, and each citation's source identity. Three clauses below cannot pass without it, and it is the only ticket that touches the view | | 00 | todo |
| T-4.9-02 | Nav order: Search, Integrations, About, Docs | F-4.8-D-09 | none | todo |
| T-4.9-03 | Answer status strip: `✓ Answered · 11.4s · 3 tools · 3 layers · 3 sources`, with a `Show work ▾` disclosure reopening the run's steps | F-4.8-D-05 | 01 | todo |
| T-4.9-04 | Run screen reasoning panel, the same detail while the run is live | F-4.8-D-10 | 01 | todo |
| T-4.9-05 | Sources collapse: an outer disclosure closed by default with its count, and each source card independently collapsible | F-4.8-D-01 | none | todo |
| T-4.9-06 | Source header names its layer in words: `L1 · graph`, `L2 · live`, `L3 · literature` | F-4.8-D-02 | none | todo |
| T-4.9-07 | Citation chips carry the source identity, `1 Gene 672` rather than `1` | F-4.8-D-04 | 01 | todo |
| T-4.9-08 | Follow-up moves above the rating, labelled `Continue this conversation` | F-4.8-D-11 | none | todo |
| T-4.9-09 | Trust pill states the layer count, `3 layers agreed` | F-4.8-D-12 | 01 | todo |
| T-4.9-10 | Account menu: a chip naming the account, with sign-out inside it | F-4.8-A-20 | none | todo |

Every ticket's acceptance is the matching clause in the gate, plus a mutation proving that clause can fail. The mutation step is not optional here: nine assertions-that-cannot-fail have been found in this territory already, four of them written by the lead.

MUTATION-TESTING HAZARD, learned the hard way on 2026-08-14: the mutation scripts in this repository revert with `git checkout -- frontend/src`, which discards UNCOMMITTED work. Commit before running one, or the fix under test is destroyed along with the mutation.

## What is deliberately not in this phase

Stated so each omission is arguable rather than discovered, per `goal-contracts`.

| Not built | Why |
|-----------|-----|
| The source card's `SNAPSHOT` date | `CitationPayload` has no such field; the backend never sends it. Build phase 6.0g, which is already touching the backend, adds it. Product-owner decision, 2026-08-14: build the card now without it rather than hold the card |
| The entity name in the source header (`NCBI Gene 672 · BRCA1`) | Same reason. `source` and `source_id` exist; the entity's own name does not |
| The risk REASON on a high-risk pill (`High-risk claim · gene to disease`) | `risk_tier` carries the tier only. The layer-count half of F-4.8-D-12 IS in scope, since it is derivable from the run's own tool calls |
| The guest allowance | Build phase 6.0g. It is a backend dependency, not a fidelity gap |
| Geometry and visual position | The gate reads DOM order, text and state. `order: -1` moves an element across the page while every DOM-order assertion stays green, measured 2026-08-14. Geometry belongs in `e2e/`, and this phase should add it there before it closes |

## How these were found

Nine gaps, four of them new, all surfaced on 2026-08-14 by screenshotting the running app beside the prototype in the same four states. That comparison had never been run in this repository before, and it found what 134 unit tests, 29 browser tests including a full WCAG 2.1 AA sweep, a clean typecheck, a clean production build and three independent review rounds had all missed.

It also found a live bug in the same pass, F-4.8-P-04, where an anonymous visitor was shown the whole stored-searches rail. Fixed on `develop` before this phase opened.

The transferable point, now recorded in `LEARNINGS.md`: comparing the built thing to the designed thing is a distinct check from asserting the built thing against itself, and this repository had only ever done the second.
