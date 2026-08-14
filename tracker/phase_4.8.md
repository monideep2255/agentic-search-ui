# Build phase 4.8: web UI visual design

Branch: `phase/4.8-web-ui-visual-design`
Depends on: 1.2 (merged)
Opened: 2026-08-13
Status: MERGED to `develop` as PR #41, 2026-08-13. Branch deleted.

Deliverable, from `Technical_specification.md` Section 25: MUI adoption, a real theme, and restyling the auth, chat/search, streaming-progress and citations screens built in phase 1.2. Extended by the design review that gated this phase: the approved prototype adds screens and components beyond that line, and the phase builds all of them.

## Table of contents

- [The premise](#the-premise)
- [What the design says](#what-the-design-says)
- [Tickets](#tickets)
- [Stub registry](#stub-registry)
- [Findings](#findings)
- [Carried open](#carried-open)
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
| T-4.8-01 | MUI and Emotion added, supply-chain checked per `supply-chain-security` | none | done |
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

### Judge round 1, 2026-08-13: FAIL

Fresh-context judge, 18 findings: 4 critical, 4 major, 5 moderate, 5 minor. It verified the theme independently against `colors.html` rather than trusting the gate's transcribed constants, and re-ran every gate itself.

| Id | Severity | What | State |
|----|----------|------|-------|
| F-4.8-J-01 | critical | An anonymous visitor asking ANY question was shown a fabricated, fully-cited answer: real NCBI source URL, full provenance card, "Grounded, every claim cited". Probed with "What is the capital of the USA?" and returned a confident cited answer about hereditary breast and ovarian cancer. Bypassed the phase 3.0 guardrail entirely | FIXED. All demo answer content removed. An anonymous ask now meets the sign-in wall. Gate clause 3e added, plus a counterfactual in `App.test.tsx` |
| F-4.8-J-02 | critical | A guardrail refusal and a fatal error both rendered as a BLANK answer screen. The refusal copy was computed correctly and passed only to `RunScreen`, unmounted by then. `grep -rn "failure"` returned zero consumers | FIXED. `AnswerScreen` renders refusal, failure and cap notices |
| F-4.8-J-03 | critical | `setRunId(null)` did not clear the event buffer, so the previous run's cited answer rendered under the next question. Judge reproduced a COX-1 claim under "What is the treatment for scurvy?" | FIXED. The view is gated on `runId`, closing the window at the point of use |
| F-4.8-J-04 | critical | The e2e "stop halts the run on the server" assertion could not fail: it polled `GET /v1/query/{run_id}`, which 404s, returning `null`, and `null !== "running"` passed on the first iteration. It had REPLACED a working assertion on `/__e2e__/run_status`, while the file header claimed every guarantee was preserved | FIXED. The real `task_cancelled` proof is restored, along with the client-side corroboration that was also dropped |
| F-4.8-J-05 | major | `String.includes("")` is always true, so one citation with an empty `claim_text` marked EVERY sentence as cited. Judge rendered "The moon is cheese." cited to NCBI Gene 672 with no spine gap | FIXED, gate clause 3d |
| F-4.8-J-06 | major | Only the FIRST `trust_signal` was read, so a downgraded verdict still displayed as grounded and low risk. The exact critical build phase 4.1 closed at the MCP fold, reintroduced at the UI layer | FIXED, folded worst-wins, gate clause 3d |
| F-4.8-J-07 | major | The "stop stops being offered" assertion was wrapped in `if (await stop.count())` and never executed | FIXED, and made deterministic with a poll after a race was found in the first fix |
| F-4.8-J-08 | major | The history rail switched the heading to a past question while leaving the current answer on screen | FIXED, it re-asks |
| F-4.8-J-09 | moderate | The a11y gate only ever scanned the STUBBED answer screen while claiming to cover every screen | FIXED, it signs in and scans the real one |
| F-4.8-J-10 | moderate | The duplicate-name check never visited the sign-in screen, the only place one of the two defects it named can appear | FIXED, it checks both screens |
| F-4.8-J-11 | moderate | The stub registry described the counter and omitted that the anonymous path rendered a complete fabricated answer | FIXED, with the history recorded so it is not repeated |
| F-4.8-J-12 | moderate | A `createRun` failure rendered as an empty answer screen with the exception swallowed | FIXED, the message is surfaced |
| F-4.8-J-13 | moderate | `Design_to_build_workflow.md` promised a visual-regression gate that does not exist | FIXED, corrected to the assembly clause actually built |
| F-4.8-J-14 | minor | A second citation on the same sentence is silently discarded | OPEN, acceptable for v1 but now declared here rather than undeclared |
| F-4.8-J-15 | minor | The mock's new comment said three required fields where the schema has four | FIXED |
| F-4.8-J-16 | minor | The premise gate's no-visible-stub rule blocked the honest disclosure fix for J-01 | RESOLVED by removing the fabricated content entirely, so no disclosure is needed |
| F-4.8-J-17 | minor | The stub run reported all five steps reached before starting | RESOLVED, the stub run no longer exists |
| F-4.8-J-18 | minor | `check_doc_drift.py --check` failed, 7 stale counts | FIXED, drift is clean |

Also found in the fix round, not by the judge:

| Id | What | State |
|----|------|-------|
| F-4.8-L-18 | Stopping a run navigated home, discarding everything already streamed. The phase 1.2 behaviour kept the partial result | Fixed: Stop stays on the run |
| F-4.8-L-19 | OPEN. The e2e suite failed once in five consecutive runs and passed the other four, with no captured detail. Three clean runs are not evidence of stability, and the judge listed repeated runs as something it did not check. Likely candidates are the sign-up waits and the run-landing races, several of which use short default timeouts | OPEN, needs attribution before this is called stable |

### Adversary round 1, 2026-08-13

27 findings: 3 critical, 13 major, 7 moderate, 4 minor. It built a scratch hostile backend replaying the exact shapes `write_node` emits, read from the source rather than guessed, and it attributed the open flake F-4.8-L-19 rather than leaving it environmental.

THE ROOT CAUSE, F-4.8-A-03. `_narrative_chunks` emits one token per sentence carrying `marker_ids`, the citation_id values that sentence cites, and its docstring states the contract outright: "A surface binds a token to its citation by that key, then looks up the number." That binding was discarded and re-derived with a `String.includes` heuristic against `claim_text`. One decision, five findings: A-01, A-04, A-06, A-07 and J-14. The premise gate could not see it because every fixture set `marker_ids: []`.

This is `attack-the-constraint`'s own lesson, missed: when output is wrong, read what the component was GIVEN before debugging what it produced. The binding was on the wire.

| Id | Severity | What | State |
|----|----------|------|-------|
| F-4.8-A-01 | critical | A citation with `claim_text: "cancer"` cited every sentence containing the word, including "Every patient with this cancer should stop chemotherapy immediately", under a "Grounded" pill with no spine gap. J-05 had rejected only the empty string | FIXED at the root by binding on `marker_ids` |
| F-4.8-A-02 | critical | A stale `createRun` response rendered its answer under a newer question's heading. J-03's fix closed the null window, not a late response. Reachable in two clicks via the history rail | FIXED with request sequencing on a monotonic ask counter |
| F-4.8-A-03 | critical | `marker_ids`, the wire's exact token-to-citation binding, had no production consumer | FIXED, and the gate fixtures now carry real `marker_ids` |
| F-4.8-A-04 | major | Backend splits sentences on `[.;?!]`, frontend on `[.!?]`, so a semicolon-joined claim became one segment in the wrong layer colour | FIXED: no re-splitting, one claim per token |
| F-4.8-A-05 | major | A real refusal rendered as two uncited claims with a "Not fully grounded" pill and the fallback link as dead text. `TrustSignalPayload.message`, `.fallback_link`, `.scope` and `.citation_id` exist in the Python contract and are absent from `lib/events.ts` | PARTIALLY FIXED: refusals now render as a notice. The missing wire fields are CARRIED, since widening the client contract is a contract change, not a UI fix |
| F-4.8-A-06 | major | "Grounded, every claim cited" rendered directly above a grey uncited segment | FIXED at the root, plus worst-wins folding |
| F-4.8-A-07 | major | A cited claim spanning a sentence boundary rendered entirely uncited | FIXED at the root |
| F-4.8-A-08 | major | The medical disclaimer was bypassable by keyboard alone: no focus trap, no `inert`, all 15 controls in the tab order behind it. `aria-modal="true"` told a screen reader the background was inert while it was reachable | FIXED with a focus trap; Escape deliberately does nothing |
| F-4.8-A-09 | major | A stream that failed to open hung the run screen silently for ever. `status` and `error` from `useAgentRun` were never read. J-12 closed this for `createRun` and left it one call downstream | FIXED |
| F-4.8-A-10 | major | Stop never disabled after being clicked, and the stepper kept asserting live work. `deriveStopEnabled` only clears on a terminal event, which stopping prevents. `StopButton` solved it with local `hasStopped`; reusing the helper without the state reused half the answer. THIS ATTRIBUTES F-4.8-L-19 | FIXED with a stop latch. Three consecutive clean e2e runs since |
| F-4.8-A-11 | major | Sign-out left the previous account's answer, sources, pills and history on screen, and the next account inherited the history | FIXED: sign-out clears all session state |
| F-4.8-A-12 | major | `runId` survived sign-out, so the old run's stream was re-requested with the new account's token, producing a silent 403 | FIXED |
| F-4.8-A-13 | major | Signing out mid-run froze the run screen asserting live work, and Stop then skipped `stopRun` because the token was gone | FIXED |
| F-4.8-A-14 | major | The real cap path emits token + done and no error, so the cap notice could never fire and the system's own status note rendered as an uncited claim promising "the answer below" | FIXED. The first version of this fix searched for the note in the list it had just removed it from, and that bug was caught before commit |
| F-4.8-A-15 | major | The raw backend `error.payload.message` was rendered, which `GuardrailBanner` and `CapMessage` both refuse to do on purpose; and any non-fatal error was treated as terminal | FIXED: fixed copy, and only fatal errors are terminal |
| F-4.8-A-16 | major | The entire trust surface was invisible to a screen reader, and axe reported ZERO violations. The spine was `aria-hidden`, chips were bare spans, so a cited and an uncited claim were indistinguishable | FIXED: per-claim text provenance, named chips, a live trust region |
| F-4.8-A-17 | moderate | No citation was a link; zero anchors on the answer screen | FIXED |
| F-4.8-A-18 | moderate | Two citations sharing a `display_index` produced duplicate cards, keys and testids | FIXED |
| F-4.8-A-19 | moderate | An unrecognised `risk_tier` folded DOWN to low and vanished | FIXED: unknown now outranks every known tier |
| F-4.8-A-20 | moderate | The only account control is a button labelled "Account" whose action is sign-out, with no menu and no confirmation | CARRIED: a designed account menu is a design-system change, and the design is frozen for this phase |
| F-4.8-A-21 | moderate | The allowance counter showed the signed-in user's count to the next anonymous visitor, then contradicted itself | FIXED |
| F-4.8-A-22 | moderate | Follow-ups and history re-asks hardcoded "researcher", discarding the user's depth choice; and a follow-up sends an unresolvable pronoun as a standalone query | DEPTH FIXED. The pronoun half is CARRIED to 4.5, which owns session memory and is the only thing that can resolve it |
| F-4.8-A-23 | moderate | No URL routing: no screen is shareable, bookmarkable or Back-navigable | CARRIED. Real routing is a structural change this phase's design does not specify |
| F-4.8-A-24 | moderate | `source_url` was not host-pinned client-side; an `evil.example.com` URL rendered as an NCBI record | FIXED with an allowlist, before A-17 made links clickable |
| F-4.8-A-25 | minor | `display_index` of 0 or -3 rendered as chips | FIXED |
| F-4.8-A-26 | minor | Duplicate testids and React keys | FIXED with A-18 |
| F-4.8-A-27 | minor | Navigating mid-run silently discards a completed answer | CARRIED, needs the routing of A-23 |
| F-4.8-A-28 | minor | Backend inline `[N]` markers rendered beside the UI's own chips | FIXED: markers stripped |

Six carried open: A-05's wire fields, A-20, A-22's pronoun half, A-23, A-27, and J-14 is now closed by A-03's fix. Each has a named reason above.

### Re-review round, 2026-08-13: FAIL

Third independent pass, aimed at the fix rounds rather than the phase. 11 findings, 1 critical, 3 major. It mutation-tested every gate clause the fix rounds added and confirmed all four can fail.

| Id | Severity | What | State |
|----|----------|------|-------|
| F-4.8-R-01 | critical | The A-02 sequencing fix closed the null window but not the stale one. `useAgentRun` reset its buffer in an effect, which runs after commit, so a render saw the NEW run id beside the PREVIOUS run's events. The RUN SCREEN WAS SKIPPED for every question after the first: no stepper, no tool chips, no reachable Stop on a cost-capped loop. It also re-exposed the cross-account leak, because the buffer is not App-level state | FIXED at the source: the buffer resets during render, so the stale frame cannot exist for any consumer |
| F-4.8-R-02 | major | `sessionId` survived sign-out, so two accounts sent the identical conversation key the backend groups memory under | FIXED |
| F-4.8-R-03 | major | `display_index` was validated for source cards but not for the citation chips built from the same events | FIXED: one usability rule, used by both |
| F-4.8-R-04 | major | The A-14 fix lifted ONE of three system-status notes off the spine; two disclosures still rendered as uncited claims | FIXED, and the notes are now shown as disclosures rather than dropped |
| F-4.8-R-05 | moderate | The marker-stripping regex deleted every bracketed number, so "study [12]" silently lost its citation number from the prose | FIXED: only the token's own cited markers are stripped |
| F-4.8-R-06 | moderate | The A-08 focus trap had no test anywhere, and could not have a vitest one (jsdom makes it inert). Programmatic focus still reached the app behind the gate | FIXED: the shell is `inert` while the gate is up, verified by an e2e test that was watched failing first |
| F-4.8-R-07 | moderate | No automated check anywhere scanned an answer carrying a citation chip, source card, spine segment or trust pill, which is why A-16 survived | FIXED: `e2e/trust-surface.spec.ts` scripts a real stream and scans the result |
| F-4.8-R-08 | minor | A repeated marker_id produced duplicate chips with a duplicate React key | FIXED |
| F-4.8-R-09 | minor | The two cap-note detection paths used different normalisations | CARRIED: latent, not reachable on today's wire |
| F-4.8-R-10 | minor | An e2e justification comment claimed more than the code guarantees | CARRIED: the assertion is sound, the comment overstates why |
| F-4.8-R-11 | minor | The disclaimer and depth preference survived sign-out | FIXED |

THE PART WORTH KEEPING. The gate clause written for R-01 could not fail, and neither could its rewrite. Both were caught by deliberately breaking the fix and watching the clause stay green, not by reading them. That is the fifth assertion-that-cannot-fail in this phase, and the third of mine.

The guarantee needs a real stream that really lands, which no mocked vitest harness provides, so it moved to the e2e suite where it was verified to fail with the fix disabled. The premise gate now carries an explicit pointer saying so rather than a clause that looks like coverage and is not.

Every new clause in this round was mutation-tested the same way, including the focus-trap check, which was watched failing before the `inert` fix landed.

### Post-merge visual pass, 2026-08-13

Not a review round. The product owner asked how the UI actually looks, so the application was started and screenshotted. Two defects were found by looking at it, both on `develop` after the phase had already closed green.

Neither could have been caught by anything this phase built. Every check here asserts what is on screen, never where it is: presence, role, accessible name, colour token, order, count. Both defects are position defects, and they coexisted with 147 unit tests, 17 end-to-end tests, a clean typecheck, a clean production build and a full WCAG 2.1 AA pass.

| Id | Severity | What | State |
|----|----------|------|-------|
| F-4.8-V-01 | major | Build phase 1.2's `#root { max-width: 720px }` scaffold survived the restyle, so the entire redesigned application rendered in a 720px strip with bare canvas either side and the app bar's own wordmark wrapped onto three lines. Every screen was restyled; the container they sit in was not | FIXED in `src/index.css`, plus `color-scheme: light dark`, which invited dark form controls against a single committed light palette |
| F-4.8-V-02 | major | The provenance spine's segments and the prose ran as two independently laid out columns, the track on a fixed 46px rhythm and the prose on its own line height. They drifted apart cumulatively, so by the third claim the grey uncited segment sat beside the wrong sentence. A spine that points at the wrong claim asserts a provenance that is not there, which is worse than no spine | FIXED: segment and claim are now two cells of one grid row, so a segment's height is driven by the claim it describes and they cannot drift |

Both fixes carry a mutation-tested guard, since the gap that let them through is real and will otherwise let the next one through too:

- V-01: an e2e assertion that the app bar spans more than 95 percent of the viewport. Mutation-tested by restoring the 720px constraint. CAUGHT.
- V-02: an e2e assertion that each segment vertically spans the claim it points at, measured with a Range over the claim's own text nodes. The first version of this guard compared the segment's box to the Typography's box, which are two cells of the same grid row and therefore level by construction, so it could not fail; a mutation passed it. Rewritten to measure the glyphs, then mutation-tested twice: against a displaced track (CAUGHT), and against the actual committed pre-fix component with nothing changed but the test hook (CAUGHT, at segment 1, which is where the drift starts).

That is the sixth assertion-that-cannot-fail in this phase, and the fourth of mine. The pattern is now consistent enough to be predictive rather than anecdotal: an assertion written against the structure that produced the output tends to restate it. Every one of the six was caught by breaking the code and watching the clause stay green, never by reading the clause.

The wider gap is stated plainly in "What the gate deliberately does not cover": nothing in this repository looks at the rendered page. That statement was written before either defect existed and correctly predicted both.

### Design fidelity pass, 2026-08-13

The product owner asked whether the design system was implemented correctly. Rather than answer from memory, the approved design system's own screens and component cards were screenshotted and compared against the running application, which is the comparison the premise gate cannot make: the gate asserts every colour token and type value against `foundations/colors.html` and fails the build on a nudged blue, but a token is not a layout and a layout is not a behaviour.

What matches: the palette, the type scale, the three layer colours, the app bar, the disclaimer strip, the provenance spine, the trust pills, the feedback surface, the follow-up field, the source-card field rows and the search history rail. The compact citation-chip variant is one the card explicitly sanctions.

Five gaps, all real, none of them a token drift.

| Id | What the design says | What shipped |
|----|----------------------|--------------|
| F-4.8-D-01 | Source rows are collapsed, one expanded at a time, "click a row to open it" | Every source card is always expanded, so a six-source answer is a wall of fields and the sources stop being scannable |
| F-4.8-D-02 | The source header names the entity and the layer in words: `[1] NCBI Gene 672 · BRCA1` on the left, `L1 · graph` on the right | `[1] NCBI Gene 672` and a bare `L1`. A reader has to already know what L1 means, which defeats the point of the layer system |
| F-4.8-D-03 | The expanded card carries six fields including `SNAPSHOT`, the date the graph row was ingested | Five fields, no snapshot. This one has weight beyond fidelity: the freshness argument in Section 7 is what lets a reader tell a graph value from a live one, and the date is where that argument is visible |
| F-4.8-D-04 | In prose, a citation chip carries the record id beside the number, `1 Gene 672` | The compact number-only variant everywhere. Sanctioned by the card, but it is the lesser variant, and the design uses the id-bearing one in running text |
| F-4.8-D-05 | The status strip reads `Answered · 11.4s · 3 tools · 3 layers · 3 sources` with a `Show work` disclosure that reopens the pipeline detail | `2 tools · 2 layers · 2 sources`. No verdict word, no elapsed time, and no way to reopen the work after the run screen is gone |

F-4.8-D-03's `TOOL` label, where the design says `EDGE`, is deliberate and is not counted as a gap: the design card was drawn for a graph edge, and the shipped card serves seven tools across three layers, where naming the tool is the more honest field. The missing snapshot date is the real defect in that row.

None of these was caught by any check, for the same reason as F-4.8-V-01 and F-4.8-V-02: the premise gate asserts the design system's TOKENS, which is what a fixture can cheaply assert, and nothing asserts its LAYOUT or its BEHAVIOUR. A design system used as a premise-gate fixture buys less than it appears to unless something compares the rendered result to it.

### Product owner review, 2026-08-13: three gaps against the design system

Found by the product owner using the running application. All three are places where the built page does not reach the approved design system's baseline, which is the stated bar: meet it first, then modify from it.

| Id | What the design says | What shipped | Why it happened |
|----|----------------------|--------------|-----------------|
| F-4.8-P-01 | A visitor gets a run of free searches, and only then is asked to sign in. The allowance is the entry experience | No search is possible at all without signing in. The sign-in wall is the first thing a visitor meets | An over-correction of judge round 1's critical finding. That finding was that an anonymous visitor received FABRICATED cited answers. The right fix was to remove the fabricated content and keep the allowance backed by real runs. What shipped removed the allowance too, which is a product regression traded for a correctness fix that did not require it |
| F-4.8-P-02 | Sign-in sits at the top right of the app bar | Present, but reached only after the wall has already blocked the visitor, so it never functions as the top-right entry point the design intends | Follows from F-4.8-P-01 |
| F-4.8-P-03 | Once signed in, a left rail holds stored searches, with a hamburger control to collapse it | The rail exists and holds searches; there is no hamburger, so it cannot be collapsed and does not adapt | Not built. No ticket owned the collapse control |

F-4.8-P-01 is the one with a real open question behind it, and it must be answered before the fix, not assumed: whether the API accepts a run from an unauthenticated caller at all. Build phase 1.1 put auth in front of the run endpoints, so a guest allowance backed by REAL searches may need a backend change, and a guest allowance backed by anything other than real searches is the exact defect judge round 1 filed. Establish which of the two it is first. If the backend cannot serve a guest run today, that is a dependency to name, not a reason to fabricate.

Sequencing agreed with the product owner: reach the design system's baseline first, then modify from it. These three come before the five fidelity gaps above, since they concern the entry path rather than the answer's presentation.

### Disposition, 2026-08-14: the open question settled, P-03 closed

The open question behind F-4.8-P-01 is answered, by probing rather than by reading: the API does NOT accept a run from an unauthenticated caller, so the guest allowance is a backend dependency and not a frontend fix.

Evidence, all four run endpoints called with no `Authorization` header:

| Endpoint | Result |
|----------|--------|
| `POST /v1/query` | 401, `{"detail":"invalid or expired access token"}` |
| `GET /v1/query/{run_id}/events` | 401, same |
| `GET /v1/query/{run_id}/citations` | 401, same |
| `POST /v1/query/{run_id}/stop` | 401, same |

Every one takes `current_user: User = Depends(get_current_user)`, which rejects a missing header before any other check (`auth/dependencies.py`, `resolve_user_from_bearer_token`). A search across `src/` for a guest, anonymous or allowance path returns nothing outside unrelated comments.

Three things that shape what happens next:

- The repository already knew. `frontend/src/stubs/registry.ts` declares the `guest-allowance` surface as `wiredBy: "6.0"`, with `realSource` naming "server-side rate limiting plus an anonymous run path". The over-correction was recorded at the time, not hidden.
- It is in v1 scope, merely unbuilt. The locked technical specification already anticipates it: `interactions.user_id` is nullable "because a session can start before login (an anonymous first query on the workspace home)" (Section 15), and Section 14.2 describes an anonymous prototype session. There is no scope-boundary question here.
- The UI half already exists and is styled to the design card. `GuestAllowance` (the five dots) and `SignInWall` are built. Nothing is missing on screen; there is no truthful data to drive them.

What a real allowance costs, priced so the deferral is an informed one rather than a shrug: a guest identity the server can trust, since the counter must be enforced server-side or it is a number a reload resets, which is the same dishonesty class judge round 1 filed; run ownership for a caller with no `users` row, which `_get_owned_run` currently derives from `current_user.id`; and a bound on anonymous run creation, already filed as F-4.0-A-10 and already owned by build phase 6.0.

Product owner's call, 2026-08-14: name the dependency, deliver F-4.8-P-03 alone. F-4.8-P-01 and F-4.8-P-02 stay open with build phase 6.0 named as the owner, since 6.0 already carries both the anonymous run path and the rate limiting the allowance depends on.

F-4.8-P-02 needs no independent code change and is not partially delivered here. `AppShell` already renders "Log in" at the top right of the bar for a signed-out visitor, matching `components/app-bar.html`. It is dysfunctional only because the wall intercepts the visitor first, so it closes when P-01 closes and not before.

F-4.8-P-03 is CLOSED on `fix/4.8-rail-collapse-control`. All three of the prototype's parts landed: the app bar toggle (`#railBtn`), the in-rail minimise button (`.rmin`), and the 46px strip with a count that a collapsed rail leaves behind (`#railStub`). One piece of state in `App` drives all three, held above the rail because a collapsed choice must survive the rail unmounting and must outlive the next question. Availability follows the prototype's `avail = st.loggedIn && onSearch`, plus this app's existing rule that an empty rail renders nothing, so a toggle is never offered for a rail that is not on screen.

### What this fix changes about how the phase checks itself

The phase's standing complaint is that every check here asserts what is on screen and never where it is. That is what this fix's gate was written against, and mutation-testing measured the gap rather than assuming it.

| Gate | Clauses | Mutation result |
|------|---------|-----------------|
| `frontend/src/railCollapsePremise.test.tsx` | 11, written first and watched failing at 10 of 11 | 9 mutations, every clause proven able to fail |
| `frontend/e2e/rail-collapse.spec.ts` | 5, bounding-box geometry in a real browser | 5 mutations, all red |

Two defects were found in the gate itself while watching it fail, before any reviewer saw it:

- One clause compared the rail's position against `<main>`, when the rail is a DESCENDANT of `<main>` in this app rather than its sibling as in the prototype. `compareDocumentPosition` returns `CONTAINED_BY` there, so the clause asserted nothing. Re-anchored on the screen's own heading.
- One clause passed vacuously by asserting only an absence, which is true of a control that was never built. It now asserts presence first and then absence after sign-out. This is the same shape that failed this phase's stub-marker test on its first run and build phase 4.1's judge round 1.

The finding worth carrying past this fix: the vitest gate CANNOT see visual position. Adding `order: -1` to the content column moves the rail to the visual right of the page and every DOM-order clause stays green. That is not a hypothetical, it is mutation M9's measured result. `e2e/rail-collapse.spec.ts` exists because of it and is mutation-tested against that exact case, and the vitest gate's coverage statement now says so rather than implying it covers position.

### Two fidelity differences found while doing this, filed rather than fixed

Both are pre-existing, both are outside the collapse control's scope, and neither is silently closed.

| Id | What the prototype says | What ships | Note |
|----|------------------------|-----------|------|
| F-4.8-D-06 | `#rail` is `--surface` (white) at 248px wide | The rail is `surfaceSunk` (#F7F8F9) at 240px | The strip added here deliberately uses `surfaceSunk` to match the RAIL IT REPLACES rather than the prototype's white `#railStub`, so one control does not change colour as it collapses. Transcribing the strip literally would have made the mismatch visible instead of latent |
| F-4.8-D-07 | The rail renders with an empty-state message when a signed-in user has no history | The rail renders nothing at all when empty | A deliberate shipped choice ("an empty rail on a first visit is furniture"), which is a reasonable call and still a difference from the approved design. Needs a product-owner decision, not a unilateral fix |

## Carried open

Eight findings, each with a named owner, so none is a silent deferral.

| Id | What | Owner |
|----|------|-------|
| F-4.8-A-05 | `TrustSignalPayload.message`, `.fallback_link`, `.scope` and `.citation_id` exist in the Python contract and are absent from `lib/events.ts`, so a refusal's structured payload is validated and ignored. Section 8.4 requires a refusal to carry somewhere to go next | Whichever phase next widens the client event contract; this is a contract change, not a UI fix |
| F-4.8-A-20 | The only account control is a button labelled "Account" whose action is sign-out, with no menu and no confirmation. T-4.8-03 named an account menu | A design pass, since the design system is frozen for this phase |
| F-4.8-A-22 | A canned follow-up sends an unresolvable pronoun ("What variants cause it?") as a standalone backend query with no prior context | 4.5, the only phase that can resolve it, since it owns session memory |
| F-4.8-A-23 | No URL routing: no screen is shareable, bookmarkable or Back-navigable, and a reload discards an answer | A structural change this phase's approved design does not specify |
| F-4.8-A-27 | Navigating to Docs or About mid-run silently discards a completed answer | Depends on A-23's routing |
| F-4.8-J-14 | Superseded and CLOSED by the `marker_ids` binding, which keeps every citation a claim declares | Closed |
| F-4.8-R-09 | The two cap-note detection paths use different normalisations. Latent: not reachable on today's wire | Whenever either path is next touched |
| F-4.8-R-10 | An e2e justification comment claims more than the code guarantees. The assertion is sound; the reasoning overstates why | Cosmetic, fix when next editing that file |
| F-4.8-L-17 | 10 modules remain orphaned with 36 tests exercising code the app no longer renders. Their green tests inflate the suite's number | Needs a product-owner decision on deletion, per `file-protection` |

## History

- 2026-08-13: post-merge visual pass on `develop`. Two position defects found by starting the application and looking at it, F-4.8-V-01 and F-4.8-V-02, both major, both fixed with a mutation-tested guard. Neither was reachable by any check this phase built, and the phase's own gate had already declared that gap in writing.

- 2026-08-13: merged to `develop` as PR #41, commit `2422131`, no squash so the eleven commits and their reasoning survive. Post-merge verification run on `develop` before pushing: vitest 147, typecheck clean, production build succeeds, doc drift clean. Remote advance proved by comparing local and remote HEAD hashes rather than trusting the push output. Phase branch deleted locally and on the remote.

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
