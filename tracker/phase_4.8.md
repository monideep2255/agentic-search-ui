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
| T-4.8-02 | `theme.ts` generated from `foundations/` tokens, the single source of colour, type and spacing | 01 | done |
| T-4.8-03 | DONE. App shell: app bar with logo, nav, persona chip and account menu; disclaimer strip; history rail; footer | 02 | done |
| T-4.8-04 | DONE. Home screen: hero, search bar, seed chips, depth control, stats row | 02 | done |
| T-4.8-05 | DONE. Run screen: pipeline stepper, tool chips, persona caption, stop button | 02 | done |
| T-4.8-06 | DONE. Answer screen: provenance spine, streamed answer, citation chips, source cards, trust pills | 02 | done |
| T-4.8-07 | DONE. Feedback surface: rating, reason chips, per-citation flag | 06 | done |
| T-4.8-08 | DONE. Guest flow: allowance counter, soft prompt, sign-in wall | 03 | done |
| T-4.8-09 | DONE. Follow-up question input with hints, and the history rail's contents | 03, 06 | done |
| T-4.8-10 | DONE. Disclaimer modal and sign-in modal | 03 | done |
| T-4.8-11 | DONE. Integrations, docs and about screens | 03 | done |
| T-4.8-12 | DONE. Assembly: every screen wired into the real app, real routing, real SSE, landing reachable without a token | 03 to 11 | done |
| T-4.8-13 | DONE. Accessibility pass: WCAG 2.1 AA across every screen, axe-clean | 12 | done |
| T-4.8-14 | DONE. Stub registry: one module listing every stubbed surface and its owning phase | 07, 08, 09 | done |

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

No judge or adversary round has run yet. Everything below was found by the lead
while building, which means none of it has been independently reviewed.

| Id | What | State |
|----|------|-------|
| F-4.8-L-01 | The first assembly replaced `createRun` with a demo timeline. Every screen rendered, navigation worked, and all 13 gate clauses passed while nothing connected the UI to the agent. The gate asserted rendering and never wiring | Fixed. Real path restored, gate clause 3b added so it cannot regress, coverage statement corrected |
| F-4.8-L-02 | The stub-marker gate test passed vacuously on its first run: it asserted only an absence, against an app that rendered almost nothing | Fixed. Presence assertions now run first |
| F-4.8-L-03 | The navigation landmark was unlabelled, so "Search" in the bar and "Search" on the form were indistinguishable | Fixed. Landmark labelled, and the form action renamed to "Ask" |
| F-4.8-L-04 | The app bar offered "Log in" while the sign-in form was already open | Fixed. `hideAuthAction` |
| F-4.8-L-05 | Persona chip label failed WCAG AA: `inkOnNavyMute` on the chip's composited ground measures about 2.7:1 | Fixed. Raised to `inkOnNavy`, 5.4:1 |
| F-4.8-L-06 | Scrollable `<pre>` code blocks were not keyboard-focusable, so a keyboard user could not scroll to read them | Fixed. `tabIndex`, `role`, `aria-label` |
| F-4.8-L-07 | DESIGN SYSTEM DEFECT. `inkFaint` measures 4.73:1 on white (passes AA) but 4.31:1 on `surfaceSunk` (fails). The token is safe on one surface and unsafe on another, and nothing in the design system says so | Usage fixed; TOKEN NOT CHANGED, because the design system is frozen for this phase. Carry to the next design pass |
| F-4.8-L-08 | PRE-EXISTING, not this phase. `GuardrailBanner`'s exhaustive category Record was missing `write_seeking`, so `tsc -b` and therefore `npm run build` had been failing on `develop` since Step 6.2 added that member. Unnoticed because no CI runs the frontend build | Fixed here incidentally. Confirmed on `develop` by stashing, not assumed |
| F-4.8-L-09 | PRE-EXISTING, and misdiagnosed for five phases. The Playwright webServer timeout carried since build phase 3.3 as "an environment quirk" was Vite binding to `[::1]` while Playwright probes `127.0.0.1`. The earlier diagnosis tested `localhost`, which resolves to `::1` on macOS, so it confirmed a different address than the failing one | Fixed. `--host 127.0.0.1` in `playwright.config.ts`. The e2e suite runs for the first time since phase 3.3 |
| F-4.8-L-10 | The "Grounded" trust pill measured 4.01:1 against a 4.5:1 requirement: ok (#2E8540) on layer2Wash (#E6F2E8). Same family as L-07, and again stated in the design system itself | Fixed by reading the label in ink while border, wash and check mark keep the green. Token unchanged, carried to the next design pass |
| F-4.8-L-11 | CRITICAL, and the largest of the phase. ChatPage and HomePage were orphaned by the new routing, and ChatPage was the ONLY consumer of the event stream. The new screens consumed no events: the stepper ran on setTimeout and the answer rendered constants, so the UI reported progress the agent had not made. createRun was called, so gate clause 3b passed | Fixed. `hooks/useRunView.ts` derives every screen's state from the events actually received. Gate clause 3c added, including the counterfactual that an empty stream must report no progress |
| F-4.8-L-12 | Guardrail refusals, cap messages and stop-button enablement were dropped entirely when the routing replaced ChatPage. All three are tested build phase 1.2 behaviours | Fixed by REUSING the reviewed helpers rather than paraphrasing them. CATEGORY_COPY is deliberately interpolation-free so a cost figure can never reach a refusal message; reimplementing it would have discarded that guarantee silently |
| F-4.8-L-13 | AuthGate rendered its own `<main>` while AppShell already owned one, so the sign-in screen carried two main landmarks, which is invalid. The accessibility suite never visited that screen, so axe never saw it | Fixed: a labelled `<section>`. The suite now covers the sign-in screen, closing the coverage gap that hid it |
| F-4.8-L-14 | The stepper reported every step as pending once a run landed, because it tracked only the live step and a finished run has none. What a run DID was not recoverable from where it IS | Fixed. `reachedSteps` is derived from the events that actually occurred |
| F-4.8-L-15 | The answer screen offered no way back to the landing; the run screen always had one, so the flow dead-ended exactly when a user finished reading | Fixed |
| F-4.8-L-16 | PRE-EXISTING, and the headline of the phase. This repository has had no working end-to-end browser test since build phase 3.0. Phase 3.0 replaced the passthrough guardrail with a real classifier that parses the Guard tier response as JSON; `tests/e2e_support/mock_llm_backend.py` returns the bare string "ok", correct when written for phase 1.2. Every run through it has died at the guard step since. Invisible because phase 3.3's webServer timeout (F-4.8-L-09) meant the suite could not start at all | Fixed: the mock is tier-aware and returns a schema-valid classification. A run now streams guard, think, plan, token, done for the first time since phase 3.0. THIS CHANGE IS A TEST-DOUBLE EDIT AND IS EXPLICITLY REFERRED TO THE JUDGE, since `goal-contracts` forbids changing a check to make it pass; the argument for legitimacy is that the double had drifted from the contract it stands in for |
| F-4.8-L-17 | OPEN, needs a product-owner decision. 10 modules remain orphaned with 36 tests exercising code the app no longer renders: AnswerStream, ChatShell, EmptyState, LoadingSkeleton, QueryInput, QueryPipelineStepper, ChatPage, HomePage. Their green tests inflate the suite's number into a claim it does not support | Open. NOT deleted, because deletion is the product owner's call under `file-protection` |

## History

- 2026-08-13: all 15 tickets done. Premise gate 16 of 16, vitest 138 of 138, e2e 11 of 11, typecheck clean, production build succeeds. Python suite 2445 passed with 6 failures, confirmed identical on `develop` by stashing rather than assumed. Judge round dispatched with fresh context; nothing in this phase has been independently reviewed yet.
- 2026-08-13, RESUMED and completed. Fixing the misdiagnosed Playwright timeout unmasked a second, older breakage: the e2e mock backend's guard response had not matched the classifier's contract since build phase 3.0, so no browser test in this repository had run green for five phases. Both are fixed and recorded as F-4.8-L-09 and F-4.8-L-16.
- 2026-08-13, PAUSED MID-TASK at the product owner's request. Not a phase boundary. State is clean and resumable: nothing half-edited, vitest 136 of 136, typecheck clean, production build succeeds, premise gate 14 of 14. Thirteen of fifteen tickets done.

  Resume here, in order:
  1. F-4.8-L-10, the one failing accessibility check. Mid-run is clean; the landed answer screen has one unidentified violation. Reproduce with `npx playwright test e2e/accessibility.spec.ts:63`, and print the full axe node rather than trusting the list reporter, which truncates it.
  2. Three pre-existing e2e specs in `e2e/query-stream-and-stop.spec.ts` still assert the old auth-first UI and fail. They need rewriting to the new contract the same way `App.test.tsx` was: preserve every guarantee, invert only the routing assumption.
  3. Then the judge round, the adversary round, and the stage-10 gates.

  Nothing has been independently reviewed yet. Every finding above was found by the lead, which is exactly the condition LEARNINGS.md warns about: a same-session self-check is not an independent review.

- 2026-08-13: T-4.8-00 done. Premise gate written before any build code and watched failing: 13 of 13, each failure naming the ticket that owes it. Two gate-integrity problems were found and fixed while writing it, before any reviewer saw it. First, static imports of not-yet-existing modules failed the whole suite at transform time, reporting "0 tests", which proves nothing about whether the assertions can fail; imports now resolve at runtime so each clause fails on its own. Second, the stub-marker test passed vacuously on the first run, because it only asserted an ABSENCE and today's `App.tsx` renders almost nothing; presence assertions now run first, so it cannot pass until the real UI is on screen. That is the same defect shape that failed build phase 4.1's judge round 1. Existing frontend suite measured green at 120 of 120 as the baseline this phase must not break.
- 2026-08-13: phase opened on `phase/4.8-web-ui-visual-design`. Design review closed first and its artifacts committed as `95e8f85`. Learnings recall run against frontend territory; build phase 1.2's scaffold-without-wiring entry drove T-4.8-12 into the decomposition up front rather than at the end.
