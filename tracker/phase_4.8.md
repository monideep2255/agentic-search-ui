# Build phase 4.8: web UI visual design

Branch: `phase/4.8-web-ui-visual-design`
Depends on: 1.2 (merged)
Opened: 2026-08-13
Status: in progress

Deliverable, from `Technical_specification.md` Section 25: MUI adoption, a real theme, and restyling the auth, chat/search, streaming-progress and citations screens built in phase 1.2. Extended by the design review that gated this phase: the approved prototype adds screens and components beyond that line, and the phase builds all of them.

## Table of contents

- [The premise](#the-premise)
- [What the design says](#what-the-design-says)
- [Tickets](#tickets)
- [Stub registry](#stub-registry)
- [Findings](#findings)
- [History](#history)

## The premise

Build phase 4.8 is a restyle. The claim it has to earn, stated so it can fail:

> Every screen in the approved prototype exists in the running React app, built from the design system's own tokens rather than approximations of them, and the 120 existing frontend tests still pass because no behaviour changed.

Four things make that testable, in descending order of how load-bearing they are:

1. Token conformance. The MUI theme's palette equals the hex values in `design-system/foundations/colors.html` exactly. A nudged blue fails the gate.
2. Structure. Each restyled component still renders the elements its contract requires: a citation chip carries its layer, a source card renders every provenance field, the pipeline stepper renders all five steps.
3. Contrast. WCAG 2.1 AA on every token pair the app actually uses, checked with `@axe-core/playwright`, which is already a dependency.
4. Assembly. The app renders the landing screen for a visitor with no token, and a question submitted there reaches the real SSE stream. This one is separate on purpose, see below.

### Why assembly is its own clause

`LEARNINGS.md`'s 2026-07-28 entry records build phase 1.2 shipping six chat components that each passed their own tests while `ChatPage.tsx` stayed a placeholder wired to nothing, because no ticket owned the wiring. Its general lesson is that a scaffold-and-integrate decomposition needs the wiring ticket named at the same time as the scaffold tickets, not discovered later.

This phase has exactly that shape, so T-4.8-12 exists from the start and the premise names assembly explicitly. Twelve green component tickets and an app that still looks like the old one is the failure mode this clause exists to catch.

### What the gate deliberately does not cover

Stated so the gap is arguable rather than discovered, per `goal-contracts`:

- It does not check that a stubbed surface returns correct data, only that it renders and is registered. Correctness arrives with the phase that wires it.
- It does not check visual fidelity pixel for pixel. It checks tokens, structure and contrast. A layout that satisfies all three and still looks wrong is possible, and that is what the judge and adversary rounds are for.
- It does not exercise the docs screen's prose for accuracy against the live API. Nothing automated can, and the content is owned by T-4.8-11.

## What the design says

The approved prototype and the component cards are the fixture. Read `docs/build/design/Design_to_build_workflow.md` first; it governs how a design change reaches this phase and what one costs now that the phase is open.

Frozen for the duration of this phase, per that document. A design change from here reopens the affected tickets and is a deliberate decision, not a pull.

Screens: landing, run, answer, wall, integrations, docs, about. Docs sub-pages: start, access, rest, mcp, kgx, cli, limits.

## Tickets

| Id | Deliverable | Depends on | Status |
|----|-------------|------------|--------|
| T-4.8-00 | The premise gate, written first and watched failing | none | done |
| T-4.8-01 | MUI and Emotion added, supply-chain checked per `supply-chain-security` | none | open |
| T-4.8-02 | `theme.ts` generated from `foundations/` tokens, the single source of colour, type and spacing | 01 | open |
| T-4.8-03 | App shell: app bar with logo, nav, persona chip and account menu; disclaimer strip; history rail; footer | 02 | open |
| T-4.8-04 | Home screen: hero, search bar, seed chips, depth control, stats row | 02 | open |
| T-4.8-05 | Run screen: pipeline stepper, tool chips, persona caption, stop button | 02 | open |
| T-4.8-06 | Answer screen: provenance spine, streamed answer, citation chips, source cards, trust pills | 02 | open |
| T-4.8-07 | Feedback surface: rating, reason chips, per-citation flag | 06 | open |
| T-4.8-08 | Guest flow: allowance counter, soft prompt, sign-in wall | 03 | open |
| T-4.8-09 | Follow-up question input with hints, and the history rail's contents | 03, 06 | open |
| T-4.8-10 | Disclaimer modal and sign-in modal | 03 | open |
| T-4.8-11 | Integrations, docs and about screens | 03 | open |
| T-4.8-12 | Assembly: every screen wired into the real app, real routing, real SSE, landing reachable without a token | 03 to 11 | open |
| T-4.8-13 | Accessibility pass: WCAG 2.1 AA across every screen, axe-clean | 12 | open |
| T-4.8-14 | Stub registry: one module listing every stubbed surface and its owning phase | 07, 08, 09 | open |

### The structural change hiding in T-4.8-12

`App.tsx` currently renders `AuthGate` and nothing else until a token resolves, so the landing screen is unreachable for a visitor without an account. The approved design makes the landing the entry point, with an allowance before sign-in is required. That is a routing change rather than a restyle, and it is why assembly is a ticket rather than a final tidy-up.

## Stub registry

Surfaces this phase builds visually against a local stub, with the phase that wires each one. T-4.8-14 turns this table into a module so the wiring phases can find them without a search.

| Surface | Ticket | Wired by |
|---------|--------|----------|
| Named scientist persona, and the per-step narrative caption | 03, 05 | 4.5 |
| Audience depth control | 04 | 4.5 |
| Follow-up questions and their hints | 09 | 4.5 |
| Conversation history and archiving | 09 | 4.5 session, 4.6 persistence |
| Feedback rating, reasons, per-citation flag | 07 | 4.6 |
| Guest allowance limit | 08 | 6.0 |
| KGX export request | 11 | 4.4 |

## Findings

None yet. Populated by the judge and adversary rounds.

## History

- 2026-08-13: T-4.8-00 done. Premise gate written before any build code and watched failing: 13 of 13, each failure naming the ticket that owes it. Two gate-integrity problems were found and fixed while writing it, before any reviewer saw it. First, static imports of not-yet-existing modules failed the whole suite at transform time, reporting "0 tests", which proves nothing about whether the assertions can fail; imports now resolve at runtime so each clause fails on its own. Second, the stub-marker test passed vacuously on the first run, because it only asserted an ABSENCE and today's `App.tsx` renders almost nothing; presence assertions now run first, so it cannot pass until the real UI is on screen. That is the same defect shape that failed build phase 4.1's judge round 1. Existing frontend suite measured green at 120 of 120 as the baseline this phase must not break.
- 2026-08-13: phase opened on `phase/4.8-web-ui-visual-design`. Design review closed first and its artifacts committed as `95e8f85`. Learnings recall run against frontend territory; build phase 1.2's scaffold-without-wiring entry drove T-4.8-12 into the decomposition up front rather than at the end.
