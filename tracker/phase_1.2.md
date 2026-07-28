# Phase 1.2: React shell and SSE

Branch: `phase/1.2-react-shell-sse`
Depends on: 1.0 (done, merged as PR #5)
Delivers (Technical_specification.md Section 25, line 3180): React shell, SSE consumption of the event stream, an empty chat endpoint wired end to end, the stop button.

Dependency check at open: Section 25's dependency graph gives 1.2 a single incoming edge from 1.0, which is `done` on `tracker/BOARD.md` and merged into `main`. This phase can start.

`product_refine` cleared at open by explicit product-owner decision, without recovering the original question (unrecorded on the board, unrecoverable by either the product owner or the lead). Logged in `DECISIONS.md`. Not re-litigated here.

## Scope note, decided at open

Section 13.1 of the tech spec describes the FULL production REST plus SSE API: a separate `POST /v1/query` (returns `run_id` immediately), `GET /v1/query/{run_id}/events` (resumable via `Last-Event-ID`), `POST /v1/query/{run_id}/stop`, `GET /v1/query/{run_id}/citations`, and `operator_mode` derived strictly from the caller's authenticated role, never a client-supplied field. Section 25 assigns that as build phase 4.0's deliverable explicitly: "The REST plus SSE adapter finalized as the public API surface." Phase 1.2's own Section 25 line is narrower: "React shell, SSE consumption of the event stream, an empty chat endpoint wired end to end, the stop button."

This phase builds the minimal REAL version of that shape, not the finalized one:

- A genuine run_id, a background task, and a real SSE stream (not the finalized resumability, not the citations export endpoint, not auth-derived-only `operator_mode`).
- `core/run.py` changes from fully-buffered (`await compiled_graph.ainvoke(...)`, collect every event, return once) to genuinely incremental (`compiled_graph.astream(..., stream_mode="updates")`, yielding each node's events as that node completes). This is the exact "ideal fix" flagged as future work in F-2.0-11's closure note in `tracker/phase_2.0.md`; this phase is where it lands.
- The existing `POST /query` endpoint (buffered, whole-array response) stays as-is; a new streaming path is added alongside it, not a replacement. Reworking `/query` itself into the finalized shape is phase 4.0's job.

Explicitly OUT of scope for this phase's frontend, each deferred to the phase that actually produces the data it needs, per `v1-scope-boundary.md`'s discipline against building a component before its backing data exists:

- `CitationChip` / `CitationPanel`: no real `citation` event exists until phase 2.2 (write-step-grounding) and 3.4 (full citation trust). Building the chip now would render against fabricated data.
- `PersonaHeader`'s real persona assignment: phase 4.5 (personalization and memory).
- `FeedbackButtons`: phase 4.6 (feedback capture).
- `TrustSignalBadge`'s real trust computation: phase 2.2 first produces a real `trust_signal` event; this phase's stub write step already emits one (`answer`/`flag`/`refuse`) per phase 2.0, so the badge can render the enum, but the underlying signal is still a stub until 2.2.
- The full WCAG 2.1 AA audit (Section 12.10): reasonable-effort accessibility on what IS built this phase (semantic HTML, keyboard operability, ARIA live region on the streaming narrative), not a formal audit, which is explicitly a production-track item per the PRD.
- `AudienceDepthToggle` and `MedicalDisclaimerModal`: no backend behavior depends on them yet (audience-level synthesis is phase 4.5's job), so they are built as inert UI controls only if a ticket has room, not required for this phase's acceptance criteria.

LEARNINGS.md filtered to this phase: no entry is tool-specific to React, Vite, SSE, or Playwright yet, since this is the first phase to touch any of them. General-process entries that still bind: use the Edit tool for board and doc files, never `sed` or a heredoc; re-verify any worktree-isolated builder's test run in the target checkout; a documented "defer to a later ticket" reasoning must be re-checked against what actually ships in the SAME phase; an acceptance criterion for a stated property must be worded as the property itself, not the mechanism; a builder must never edit its own ticket's `Status` field in the tracker to `done` (2026-07-28 build phase 2.0 entry); scan-secrets.sh can block a compound command over a password-shaped fragment even when no single line matches its regex in isolation, so any verification script touching credentials goes in its own file with generated (not literal) secret values.

## Tickets

### T-1.2-01: Incremental streaming via `astream`

Status: todo
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: none
Spec: Technical_specification.md Section 2.1 (`run()`), Section 13.1 (streaming intent); `tracker/phase_2.0.md` F-2.0-11's closure note

Files this ticket may create or modify:
- `src/system_03_search_agent/core/run.py`
- `src/system_03_search_agent/core/run_registry.py` (new: in-process run tracking)
- `tests/system_03_search_agent/core/test_run.py` (extend only)
- `tests/system_03_search_agent/core/test_run_registry.py` (new)

Acceptance criteria:
- [ ] A new function (e.g. `run_streaming(query, context)` or an equivalent generator) drives `compiled_graph.astream(initial_state, stream_mode="updates")` and yields each node's `events` slice as that node completes, not buffered until the whole graph finishes
- [ ] The existing `run(query, context)` (used by the existing buffered `/query` endpoint) is UNCHANGED in its public behavior: all existing tests in `test_run.py` still pass without modification to their assertions
- [ ] A real timing test proves incrementality: a test that artificially delays one node's model call (via the mocked `litellm.acompletion`) asserts that earlier nodes' events are observable by the caller BEFORE the delayed node completes, not all at once at the end
- [ ] `run_registry.py` provides: create a run (mint a `run_id`, uuid4), register a background `asyncio.Task` running the streaming graph and pushing its events into a per-run queue, look up a run by id, and cancel a run by id (idempotent: cancelling an already-finished or already-cancelled run does not raise)
- [ ] A run's ownership is tracked (the `user_id` that created it), so a later ticket's endpoint can 403 a caller that does not own the `run_id`
- [ ] The F-2.0-11 crash-fallback behavior (an otherwise-uncaught exception during the graph run yields a synthetic error/done pair rather than propagating raw) holds for the streaming path too, not just the buffered one

Breakdown:
- [ ] `astream(stream_mode="updates")` wiring, decoding each node's partial state update to its `events` slice
- [ ] `run_registry.py`: run creation, background task registration, per-run event queue, cancellation, ownership tracking
- [ ] Tests: incrementality (real timing), crash fallback on the streaming path, registry create/lookup/cancel/idempotent-cancel, ownership tracking

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 2.1/13.1 and F-2.0-11's closure note

### T-1.2-02: The three endpoints (create, stream, stop)

Status: todo
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: T-1.2-01
Spec: Technical_specification.md Section 13.1 (the minimal subset: create, events, stop; resumability and the citations endpoint are explicitly out of scope, see this file's Scope note)

Files this ticket may create or modify:
- `src/system_03_search_agent/adapters/web_sse/app.py` (add new routes; do not remove or change the existing `POST /query`)
- `tests/system_03_search_agent/adapters/web_sse/test_streaming_endpoints.py` (new)

Acceptance criteria:
- [ ] `POST /v1/query` (`{text, session_id, audience_depth?}`, same auth as the existing `/query`) constructs `Query`/`RequestContext` server-side exactly as `/query` already does (server-derived `user_id`, per T-2.0-08), starts the streaming run via `run_registry`, and returns `202 {run_id, persona_name}` immediately, before the graph has necessarily finished (a test asserts the response returns while a deliberately-slowed node is still running)
- [ ] `persona_name` is a fixed placeholder string for this phase (e.g. `"Assistant"`), since real persona assignment is phase 4.5's job; document this as a stub, not a silent omission
- [ ] `GET /v1/query/{run_id}/events` streams `text/event-stream` via `sse-starlette`'s `EventSourceResponse`, forwarding each event from the run's queue as an SSE frame (event name = the envelope's `type`, data = the JSON payload), and closes the stream after `done` or a fatal `error`
- [ ] The events endpoint 403s a caller that does not own `run_id` (a different authenticated user's token), and 404s an unknown `run_id`
- [ ] `POST /v1/query/{run_id}/stop` cancels the run's background task; calling it on an already-finished or already-stopped run returns `200` as a no-op, never an error (production-standards retry-safety gate)
- [ ] The existing cost/operator_mode filtering (`filter_events_for_end_user`, the `OPERATOR_USER_IDS` allowlist) applies identically to the new streaming path: a non-operator caller's SSE stream never carries a `cost` event or an un-redacted `done.total_cost_usd`
- [ ] The existing `POST /query` endpoint's behavior and tests are completely unaffected by this ticket

Breakdown:
- [ ] `POST /v1/query`: run creation, 202 response
- [ ] `GET /v1/query/{run_id}/events`: SSE streaming via `sse-starlette`, ownership check, cost filtering
- [ ] `POST /v1/query/{run_id}/stop`: cancellation, idempotent
- [ ] Tests: 202-before-completion timing, ownership 403, unknown-run 404, idempotent stop, cost filtering on the streaming path

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 13.1's minimal subset

### T-1.2-03: React app scaffold

Status: todo
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: none
Spec: Technical_specification.md Section 12.1 (component architecture, module lineage); Section 1.6 (`frontend/` as a separate top-level directory)

Files this ticket may create or modify:
- `frontend/` (new: entire Vite + React + TypeScript scaffold)
- `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`
- `frontend/src/pages/HomePage.tsx`, `frontend/src/pages/ChatPage.tsx`
- `frontend/src/components/chat/ChatShell.tsx`, `frontend/src/components/chat/QueryInput.tsx`, `frontend/src/components/chat/EmptyState.tsx`
- `.gitignore` (add `frontend/node_modules/`, `frontend/dist/` if not already covered by the existing `frontend/build/` or `frontend/dist/` pattern; verify first, do not duplicate)

Acceptance criteria:
- [ ] `npm install && npm run dev` starts a working Vite dev server with no errors
- [ ] TypeScript strict mode is enabled (`tsconfig.json`); no `any` type anywhere without an explicit, commented justification (production-standards code-quality gate)
- [ ] `HomePage` renders an empty state (`EmptyState`) with a `QueryInput`; submitting a non-empty query navigates to `ChatPage`
- [ ] `ChatShell` holds the current run's state (a `run_id` once created, session state) as the page layout wrapper
- [ ] `QueryInput` has an explicit `<label>`, never a placeholder-only affordance (Section 12.10, success criterion 3.3.2), and is keyboard-operable (Tab, Enter submits)
- [ ] Every new npm dependency added by this ticket passes `supply-chain-security.md`'s pre-install checks (no compromise reports, no unexplained postinstall script, `npm audit` clean) before being committed; document which packages were checked in the ticket's evidence

Breakdown:
- [ ] Vite + React + TypeScript scaffold, strict mode, dev server
- [ ] `HomePage`, `EmptyState`, `QueryInput`, `ChatShell`, `ChatPage` (routing between them)
- [ ] `npm audit` and per-package supply-chain check for every new dependency

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 12.1/1.6

### T-1.2-04: Typed SSE consumption (`lib/events.ts`, `lib/api.ts`, `useAgentRun`)

Status: todo
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: T-1.2-02, T-1.2-03
Spec: Technical_specification.md Section 12.2 (SSE consumption: the event dispatcher, including the exact `AgentEvent` union and `useAgentRun` shape)

Files this ticket may create or modify:
- `frontend/src/lib/events.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/hooks/useAgentRun.ts`
- `frontend/src/lib/events.test.ts`, `frontend/src/hooks/useAgentRun.test.ts` (new)

Acceptance criteria:
- [ ] `lib/events.ts`'s `AgentEvent` union mirrors Section 2.3's payload shapes field-for-field for every type EXCEPT `cost` (which has no client-side variant at all, per Section 12.2's own note, since it is server-filtered before it ever reaches this client in the non-operator case this phase targets)
- [ ] `lib/api.ts` provides typed wrappers: create a run (`POST /v1/query`), stop a run (`POST /v1/query/{run_id}/stop`)
- [ ] `useAgentRun(runId)` opens one `EventSource` against `GET /v1/query/{run_id}/events`, registers a listener per known event type (matching Section 12.2's `knownTypes` list minus `cost`), and dispatches into a reducer/state array in arrival order
- [ ] The hook closes its `EventSource` when `done` arrives, or when an `error` event with `fatal: true` arrives; it does NOT close on a non-fatal `error` (matching Section 12.2's `fatal`-only branching, never reading a nonexistent `code` or `recoverable` field)
- [ ] The hook closes its `EventSource` on unmount (React cleanup), so navigating away from an active run does not leak an open connection
- [ ] A real integration test (mocking `EventSource` or using a test server, builder's choice, documented) proves events dispatch in the order the server sent them, not just that individual handlers are wired

Breakdown:
- [ ] `lib/events.ts` typed union
- [ ] `lib/api.ts` typed fetch wrappers
- [ ] `useAgentRun.ts` hook: EventSource lifecycle, dispatch, fatal-close logic, unmount cleanup
- [ ] Tests: union shape matches the real backend payloads (cross-check against a live or mocked `/events` response), ordering, fatal vs non-fatal close, unmount cleanup

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 12.2

### T-1.2-05: The streaming stepper and answer rendering

Status: todo
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: T-1.2-04
Spec: Technical_specification.md Section 12.3 (streaming the curated narrative), Section 12.5 (loading/empty/home states), Section 12.6 (guardrail and cap messages, no dollar figures), Section 12.10 (accessibility, the subset that applies to what is built here)

Files this ticket may create or modify:
- `frontend/src/components/chat/QueryPipelineStepper.tsx`
- `frontend/src/components/chat/AnswerStream.tsx`
- `frontend/src/components/chat/GuardrailBanner.tsx`
- `frontend/src/components/chat/CapMessage.tsx`
- `frontend/src/components/chat/LoadingSkeleton.tsx`
- Corresponding `.test.tsx` files (new)

Acceptance criteria:
- [ ] `QueryPipelineStepper` renders `guard`, `think`, `plan`, `tool_start`, `tool_result` events as an ordered list of steps, each moving through pending, active, done/error states as events arrive; no `citation`-dependent rendering (out of scope this phase, per this file's Scope note)
- [ ] `AnswerStream` renders each `token.payload.text` in arrival order; it does NOT attempt to render `CitationChip` markers this phase (no real citation data exists yet), but does not crash or drop text if a token carries `marker_ids` it cannot yet resolve — it renders the marker text plainly, deferring chip rendering to whichever phase builds `CitationChip` (2.2/3.4)
- [ ] `GuardrailBanner` renders when `guard.passed` is `false`, choosing copy by `guard.category`, matching Section 12.6's table; no dollar figure, token count, or cost figure appears in any copy path (checked by grep, not just by reading the template, since the template has no interpolation slot for one)
- [ ] `CapMessage` renders on a non-fatal cap-shaped `error` event (`fatal: false`), showing the partial-result-plus-explanation copy from Section 12.6, again with no dollar figure anywhere reachable
- [ ] The streaming narrative region uses `aria-live="polite"`; `GuardrailBanner` and `CapMessage` use `role="alert"` (Section 12.10, success criterion 4.1.3)
- [ ] `LoadingSkeleton` renders during the cold-start and guard-pending states (Section 12.5), never a blank pane

Breakdown:
- [ ] `QueryPipelineStepper` with per-step pending/active/done/error states
- [ ] `AnswerStream`, plain-text token rendering, no citation dependency
- [ ] `GuardrailBanner`, `CapMessage`, both no-dollar-figure verified
- [ ] `LoadingSkeleton`, cold-start and guard-pending states
- [ ] Tests: step state transitions, token ordering, guardrail category copy, cap message copy, no-dollar-figure grep, aria-live/role=alert presence

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 12.3/12.5/12.6/12.10

### T-1.2-06: The stop button, wired end to end

Status: todo
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: T-1.2-02, T-1.2-04, T-1.2-05
Spec: Technical_specification.md Section 12.3 (`StopButton`)

Files this ticket may create or modify:
- `frontend/src/components/chat/StopButton.tsx`
- `frontend/src/components/chat/StopButton.test.tsx` (new)

Acceptance criteria:
- [ ] `StopButton` is enabled from the moment a `guard` event with `passed: true` arrives until `trust_signal`, `done`, or a fatal `error` arrives; disabled otherwise
- [ ] Clicking it calls `POST /v1/query/{run_id}/stop` AND closes the local `EventSource` immediately, not waiting on the network round trip (Section 12.3's "feels instantly responsive" requirement) — a test with an artificially slow stop-endpoint response still shows the UI as stopped immediately
- [ ] Clicking stop on an already-finished run is a no-op, matching the backend's idempotent 200 (no error toast, no crash)
- [ ] Keyboard-operable: reachable by Tab, activatable by Enter and Space (Section 12.10, success criterion 2.1.1)
- [ ] An end-to-end test (can be the Playwright test from T-1.2-07, cross-referenced here rather than duplicated) proves stopping a real, running query actually halts the server-side loop, not just the client-side UI state

Breakdown:
- [ ] `StopButton` enabled/disabled state logic
- [ ] Click handler: stop call plus immediate local `EventSource` close
- [ ] Tests: enabled-window logic, immediate-UI-response under a slow backend, idempotent double-stop, keyboard operability

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 12.3

### T-1.2-07: Playwright install and the first real E2E test

Status: todo
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: T-1.2-01, T-1.2-02, T-1.2-03, T-1.2-04, T-1.2-05, T-1.2-06
Spec: Technical_specification.md Section 23 (testing strategy, browser-driven E2E); `tracker/BOARD.md`'s "Playwright not installed" flag; `.claude/rules/supply-chain-security.md`

Files this ticket may create or modify:
- `frontend/package.json` (add `@playwright/test` as a devDependency)
- `frontend/playwright.config.ts`
- `frontend/e2e/query-stream-and-stop.spec.ts` (new)

Acceptance criteria:
- [ ] `@playwright/test` is installed pinned to the exact version verified clean this session (`1.62.0`, or a later version re-verified the same way at install time per `supply-chain-security.md`, never `@latest`, never any `playwright-1.4x`-shaped impostor package name)
- [ ] `npx playwright install` (browser binaries) runs cleanly in this environment
- [ ] One real E2E test drives a real browser against the real running frontend AND the real backend (with `litellm` mocked at the backend, same pattern every other test in this repo uses, no real API key needed): types a query, submits it, observes the pipeline stepper progress, observes the answer stream render tokens, and reaches a terminal `done` state
- [ ] A second E2E test proves the stop button: starts a query, clicks stop mid-stream, and asserts the run actually halts (no further token events arrive after the stop click, matching T-1.2-06's server-side halt requirement)
- [ ] `axe-core` (or an equivalent automated accessibility scanner) runs against the rendered `ChatPage` as part of this test suite, per Section 12.10's "automated axe-core check in CI as a baseline"

Breakdown:
- [ ] Pinned `@playwright/test` install, browser binaries, re-verified against `supply-chain-security.md` at install time (not just at this session's precheck)
- [ ] `playwright.config.ts`: base URL, dev-server startup (`webServer` config launching both the FastAPI backend with mocked LiteLLM and the Vite dev server)
- [ ] E2E test: full query-to-done flow
- [ ] E2E test: stop mid-stream actually halts the server
- [ ] `axe-core` automated accessibility scan wired into the same suite

Evidence:
- (filled at close)

History:
- 2026-07-28 lead: created, scoped from Section 23 and the standing Playwright board flag

## Findings

No findings filed yet. This section fills in as building and adversarial review happen during the phase.

## History

- 2026-07-28 lead: phase opened, dependency verified against Section 25 and `tracker/BOARD.md`, product_refine cleared by product-owner decision, LEARNINGS.md read filtered to this phase, decomposed into 7 tickets (T-1.2-01 through T-1.2-07), all refined at creation. Scope explicitly bounded against the full Section 13.1 API (deferred to phase 4.0) and against Section 12 components whose backing data does not exist until later phases (citations, persona, feedback), confirmed with the product owner before dispatch.
