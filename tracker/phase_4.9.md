# Build phase 4.9: answer-screen and chrome fidelity

Branch: `phase/4.9-answer-screen-fidelity`
Depends on: 4.8 (merged, closed out via PR #42 and PR #43)
Opened: 2026-08-14
Status: BUILD COMPLETE, THREE REVIEW ROUNDS RUN, all three returned FAIL. Gate 21 of 21 green, 15 mutations all red. A fourth round has not run.

Deliverable: close the nine fidelity gaps between the running app and the approved prototype, plus the account menu. Scheduled 2026-08-14 by product-owner decision rather than left as undated flags.

## Table of contents

- [The premise](#the-premise)
- [What shipped](#what-shipped)
- [Review rounds](#review-rounds)
- [Tickets](#tickets)
- [What is deliberately not in this phase](#what-is-deliberately-not-in-this-phase)
- [How these were found](#how-these-were-found)
- [The two product decisions this phase carried, settled](#the-two-product-decisions-this-phase-carried-settled)

## The premise

> The run and answer screens present what the approved prototype presents, in the prototype's own order, with the specifics the prototype names rather than summaries of them.

Source of truth: `docs/build/design/design-system/prototype/app.html`, `#s-answer` and its `finish()` renderer. The prototype's order is askline, `.summary` (verdict, meta, Show work), the spine and answer grid, then `#tail`: sources, verdict pills, follow-up, feedback.

The gate is `frontend/src/phase49Premise.test.tsx`. Its own coverage statement names what it does not test, including the two fields the backend cannot supply.

## What shipped

Every ticket below is done. The gate went from 12 clauses all red to 13 all green, and every clause is mutation-proven.

| Gate | Result |
|------|--------|
| `phase49Premise.test.tsx` | 21 of 21 |
| Mutations | 15 across the fix rounds, every one red, each against the check that owns it |
| vitest | 155 passed |
| Playwright | 29 passed, run serially to get the true count |
| Typecheck | Clean |
| Production build | Succeeds |
| Doc drift | 0 stale, 0 structural |

### Three defects found by looking at the rendered screen, not by any assertion

The first two are this phase's own; the third is a pre-existing trap it walked into.

- The reasoning log opened a PASSING run with "This question could not be processed." Its guard line was built from `CATEGORY_COPY`, which is refusal copy whose `ok` entry is a fallback, not a description of a guard that passed. Every one of the twelve clauses was already green when this was spotted in a screenshot. A thirteenth clause now asserts both halves, absence of the refusal text AND presence of the in-scope text, and is mutation-proven.
- The status strip was given a `surfaceSunk` tint the prototype does not have, and that tint pushed the green "✓ Answered" to 4.34:1 against a 4.5:1 requirement. Removing the tint matched the prototype and fixed the contrast in the same edit, which is the argument for transcribing rather than improvising.
- A `ReadableStream` left unclosed in this phase's own gate, to simulate a run in flight, held a reader open for the file's lifetime. Unrelated tests in other files then timed out at 15s and once at 23s while passing cleanly alone. Closing it fixed six consecutive runs.

### Two deviations from the prototype, both forced by the accessibility gate

Neither is a judgment call, and both are filed rather than taken silently: `F-4.9-D-13` and `F-4.9-D-14` on the board.

- The prototype puts the `Flag: does not support` button inside the source card's `<summary>`. axe calls that `nested-interactive`, a summary with a focusable descendant, WCAG 4.1.2. It sits in the card body instead, so a card must be open to flag it.
- The prototype's account avatar is `rgba(255,255,255,.22)`, which composites to #5F84B1 and puts white 11px bold text at 3.87:1. Shipped as `navy`, about 13:1.

That is the THIRD instance of one underlying problem, after F-4.8-D-08's two: the design system is internally inconsistent about contrast, so "matches the design" and "passes the accessibility gate" are two checks that can disagree.

### Existing checks changed, none weakened

- Two rail clauses signed out through the old "Account" button, which the menu replaced. They now sign out through the menu; the guarantee about what happens to the RAIL is untouched.
- The trust-surface helper opens the sources disclosure before asserting on a card, since cards now start collapsed.
- The rail's counts assertion was INVERTED rather than relaxed: the answer strip is now a superset of the rail's label, so the rail's counts must appear verbatim inside the strip.
- An accessibility locator moved from the text "Guard" to the stepper's own `step-Guard` hook, because the reasoning log names the steps too and a bare text match resolved to two elements intermittently.
- `testTimeout` raised from vitest's 5s default to 15s. A deadline, not an assertion: with the stream leak fixed but the default restored, three of five full runs still failed on ~5000ms timeouts, always a different set, every implicated file passing alone.

## Review rounds

Three rounds, all FAIL. Every finding was reproduced in code before being fixed; none was taken on a reviewer's word.

| Round | Verdict | Findings |
|-------|---------|----------|
| Adversary 1 | | 19: 4 critical, 6 major, 6 moderate, 3 minor |
| Judge 1 | FAIL | 14: 0 critical, 3 major, 3 moderate, 8 minor |
| Re-review of the fix round | FAIL | 14: 0 critical, 5 major, 4 moderate, 5 minor |

### What each round caught that the previous one could not

The judge's two majors were about the GATE, not the product: a count assertion that read the whole `<details>` and so survived deleting the badge it was written for (the fixture's third source id, `21990134`, contains a "3"), and a fixture collinear on every axis it asserted, where citation index equalled layer equalled card position and tools equalled layers equalled sources. Rebuilding the fixture honestly then exposed two shipped defects the old one was structurally incapable of seeing.

The re-review's value was almost entirely in the fix round itself: three of its five majors are regressions the fix round introduced. That is the pattern this repository has measured across four consecutive phases, and it held again.

- The A-05 fix MOVED the "0 layers agreed" nonsense rather than removing it, from a run with citations and no tool results to a run with tools and no citations.
- The A-01 fix collapsed every fatal class onto one sentence, so a run the USER stopped was told "This run could not be completed. Try asking again".
- The A-04 clause asserted `data-layer` alone, a test hook no user meets, while mutations reverting the chip's COLOUR and its screen-reader text both left it green. Those two were the harms the finding actually named.

### Findings not fixed, with a disposition each

The three rounds filed 47 findings. The criticals, all five majors from the re-review, and the counting defects are closed above. The rest are recorded here so none is a silent deferral, per `task-tracker`'s raiser-never-closes rule: none of these is closed, each has an owner.

| Finding | Why not now | Owner |
|---------|-------------|-------|
| F-4.9-A-08 stopped run gives no terminal signal, tool chip says "running" for ever | The backend emits a purpose-built `cancelled` event that the client aborts before it can arrive. Fixing it means changing the stop path, not the answer screen | A phase that owns the run lifecycle |
| F-4.9-A-09 the off-host citation warning is now two disclosures deep | Real, and caused by this phase's collapse. Whether a security warning may sit behind a disclosure at all is a product call, not a styling one | Product owner decision |
| F-4.9-A-16 "unlimited searches" is false against a shipped 100/day cap | A copy change that asserts a policy. Build phase 4.10 owns the allowance and its wording | 4.10 |
| F-4.9-A-07 failed tool calls counted as work | Needs a decision on whether the strip counts attempts or successes, which interacts with F-4.9-R-02's wording | 4.9 follow-up or 4.10 |
| F-4.9-A-10 to A-15, A-17 to A-19 | Moderate and minor: truncation invisible, `total_tool_calls` ignored, duplicate-index citation dropped, refusal copy duplicated | A follow-up pass on the answer screen |
| F-4.9-J-04 `L3 · trials` for a ClinicalTrials.gov source | Derivable today from the citation's own tool, and a real prototype gap this phase did not declare | 4.9 follow-up |
| F-4.9-J-05, J-06 reasoning is a heading not a `<details>`, Show work drops the tool chips | Prototype gaps, same class as the nine this phase closed | 4.9 follow-up |
| F-4.9-J-07 to J-14, F-4.9-R-06 to R-14 | Minor and moderate, including the design-system audit's own findings | A follow-up pass |

## Tickets

| Id | Deliverable | Finding | Depends on | Status |
|----|-------------|---------|------------|--------|
| T-4.9-00 | The premise gate, written first and watched failing | | none | done |
| T-4.9-01 | DONE. `useRunView` carries the run's elapsed time, its step narratives with timings, the distinct layer count, and each citation's source identity. Three clauses below cannot pass without it, and it is the only ticket that touches the view | | 00 | done |
| T-4.9-02 | DONE. Nav order: Search, Integrations, About, Docs | F-4.8-D-09 | none | done |
| T-4.9-03 | DONE. Answer status strip: `✓ Answered · 11.4s · 3 tools · 3 layers · 3 sources`, with a `Show work ▾` disclosure reopening the run's steps | F-4.8-D-05 | 01 | done |
| T-4.9-04 | DONE. Run screen reasoning panel, the same detail while the run is live | F-4.8-D-10 | 01 | done |
| T-4.9-05 | DONE. Sources collapse: an outer disclosure closed by default with its count, and each source card independently collapsible | F-4.8-D-01 | none | done |
| T-4.9-06 | DONE. Source header names its layer in words: `L1 · graph`, `L2 · live`, `L3 · literature` | F-4.8-D-02 | none | done |
| T-4.9-07 | DONE. Citation chips carry the source identity, `1 Gene 672` rather than `1` | F-4.8-D-04 | 01 | done |
| T-4.9-08 | DONE. Follow-up moves above the rating, labelled `Continue this conversation` | F-4.8-D-11 | none | done |
| T-4.9-09 | DONE. Trust pill states the layer count, `3 layers agreed` | F-4.8-D-12 | 01 | done |
| T-4.9-10 | DONE. Account menu: a chip naming the account, with sign-out inside it | F-4.8-A-20 | none | done |

Every ticket's acceptance is the matching clause in the gate, plus a mutation proving that clause can fail. The mutation step is not optional here: nine assertions-that-cannot-fail have been found in this territory already, four of them written by the lead.

MUTATION-TESTING HAZARD, learned the hard way on 2026-08-14: the mutation scripts in this repository revert with `git checkout -- frontend/src`, which discards UNCOMMITTED work. Commit before running one, or the fix under test is destroyed along with the mutation.

## What is deliberately not in this phase

Stated so each omission is arguable rather than discovered, per `goal-contracts`.

| Not built | Why |
|-----------|-----|
| The source card's `SNAPSHOT` date | `CitationPayload` has no such field; the backend never sends it. Build phase 4.10, which is already touching the backend, adds it. Product-owner decision, 2026-08-14: build the card now without it rather than hold the card |
| The entity name in the source header (`NCBI Gene 672 · BRCA1`) | Same reason. `source` and `source_id` exist; the entity's own name does not |
| The risk REASON on a high-risk pill (`High-risk claim · gene to disease`) | `risk_tier` carries the tier only. The layer-count half of F-4.8-D-12 IS in scope, since it is derivable from the run's own tool calls |
| The guest allowance | Build phase 4.10. It is a backend dependency, not a fidelity gap |
| Geometry and visual position | The gate reads DOM order, text and state. `order: -1` moves an element across the page while every DOM-order assertion stays green, measured 2026-08-14. Geometry belongs in `e2e/`, and this phase should add it there before it closes |

## How these were found

Nine gaps, four of them new, all surfaced on 2026-08-14 by screenshotting the running app beside the prototype in the same four states. That comparison had never been run in this repository before, and it found what 134 unit tests, 29 browser tests including a full WCAG 2.1 AA sweep, a clean typecheck, a clean production build and three independent review rounds had all missed.

It also found a live bug in the same pass, F-4.8-P-04, where an anonymous visitor was shown the whole stored-searches rail. Fixed on `develop` before this phase opened.

The transferable point, now recorded in `LEARNINGS.md`: comparing the built thing to the designed thing is a distinct check from asserting the built thing against itself, and this repository had only ever done the second.

## The two product decisions this phase carried, settled

Both were left open at close as genuine product calls rather than bugs, and both were answered on 2026-08-15 in a single decision session that cleared the backlog of eight such items accumulated across phases 3.1 to 4.10. Full reasoning for each is in `DECISIONS.md`; recorded here so this phase's own file does not read as though they are still open.

- F-4.9-A-09, the off-host citation warning two disclosures deep: the warning MOVES OUTSIDE the collapsed source disclosure. The person a link-goes-off-site warning protects is exactly the person who would not open two disclosures looking for it, so nesting it inverts who it reaches. The collapse itself stays for the rest of the card. Owner: the next frontend ticket.
- F-4.9-A-08, a stopped run giving no terminal signal: the client WAITS for the backend's `cancelled` event before closing the stream. That event already exists and is purpose-built; the client aborts before it can arrive, so the signal is being discarded rather than missing. Asserting a stopped state locally instead was rejected, because it is the page claiming something it has not confirmed, which is the same class as the fabricated answer this phase's own judge round filed as its first critical. Owner: the next frontend ticket.
