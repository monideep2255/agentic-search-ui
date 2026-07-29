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

Status: in-review
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
- [x] A new function (e.g. `run_streaming(query, context)` or an equivalent generator) drives `compiled_graph.astream(initial_state, stream_mode="updates")` and yields each node's `events` slice as that node completes, not buffered until the whole graph finishes
- [x] The existing `run(query, context)` (used by the existing buffered `/query` endpoint) is UNCHANGED in its public behavior: all existing tests in `test_run.py` still pass without modification to their assertions
- [x] A real timing test proves incrementality: a test that artificially delays one node's model call (via the mocked `litellm.acompletion`) asserts that earlier nodes' events are observable by the caller BEFORE the delayed node completes, not all at once at the end
- [x] `run_registry.py` provides: create a run (mint a `run_id`, uuid4), register a background `asyncio.Task` running the streaming graph and pushing its events into a per-run queue, look up a run by id, and cancel a run by id (idempotent: cancelling an already-finished or already-cancelled run does not raise)
- [x] A run's ownership is tracked (the `user_id` that created it), so a later ticket's endpoint can 403 a caller that does not own the `run_id`
- [x] The F-2.0-11 crash-fallback behavior (an otherwise-uncaught exception during the graph run yields a synthetic error/done pair rather than propagating raw) holds for the streaming path too, not just the buffered one

Breakdown:
- [x] `astream(stream_mode="updates")` wiring, decoding each node's partial state update to its `events` slice
- [x] `run_registry.py`: run creation, background task registration, per-run event queue, cancellation, ownership tracking
- [x] Tests: incrementality (real timing), crash fallback on the streaming path, registry create/lookup/cancel/idempotent-cancel, ownership tracking

Evidence (backfilled 2026-07-28 during phase close, from the judge review's independent verification, since this ticket's own evidence was never filled in when it was built and merged earlier in the same session):
- `python3 -m pytest tests/ -q`: 537 passed (whole-repo run, this ticket's suite included)
- `core/run.py:238` — `async for update in compiled_graph.astream(initial_state, stream_mode="updates")`, yielding each node's `events` slice at `:240-242`
- `run()` itself unchanged at `run.py:149-188`, still `ainvoke`-based
- Real timing test: `tests/system_03_search_agent/core/test_run.py:358` `class TestRunStreamingIsGenuinelyIncremental`, `:368` `test_earlier_events_arrive_before_a_delayed_nodes_event_by_a_real_measurable_gap`
- `run_registry.py:189-195` create (uuid4, background task, per-run queue), `:197-206` lookup (`RunNotFoundError`), `:208-230` cancel (idempotent); ownership tracked at `:193` from `query.user_id`
- Crash fallback on the streaming path at `run.py:243-246` with `start_seq=next_seq` keeping `seq` monotonic; tests at `test_run.py:412` and `:444`
- Commit 22be5b7 on `phase/1.2-react-shell-sse`

History:
- 2026-07-28 lead: created, scoped from Section 2.1/13.1 and F-2.0-11's closure note
- 2026-07-28 lead: built, merged, tests passing (real-time work this session, evidence not filled in at the time)
- 2026-07-28 judge: independently re-verified against source and the real test run during the phase-level review; PASS
- 2026-07-28 lead: backfilled Evidence and set in-review from the judge's verified findings, since the gap (built and passing, but the ticket record never updated) was the judge's top blocking finding for phase close

### T-1.2-02: The three endpoints (create, stream, stop)

Status: in-review
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: T-1.2-01
Spec: Technical_specification.md Section 13.1 (the minimal subset: create, events, stop; resumability and the citations endpoint are explicitly out of scope, see this file's Scope note)

Files this ticket may create or modify:
- `src/system_03_search_agent/adapters/web_sse/app.py` (add new routes; do not remove or change the existing `POST /query`)
- `tests/system_03_search_agent/adapters/web_sse/test_streaming_endpoints.py` (new)

Acceptance criteria:
- [x] `POST /v1/query` (`{text, session_id, audience_depth?}`, same auth as the existing `/query`) constructs `Query`/`RequestContext` server-side exactly as `/query` already does (server-derived `user_id`, per T-2.0-08), starts the streaming run via `run_registry`, and returns `202 {run_id, persona_name}` immediately, before the graph has necessarily finished (a test asserts the response returns while a deliberately-slowed node is still running)
- [x] `persona_name` is a fixed placeholder string for this phase (e.g. `"Assistant"`), since real persona assignment is phase 4.5's job; document this as a stub, not a silent omission
- [x] `GET /v1/query/{run_id}/events` streams `text/event-stream` via `sse-starlette`'s `EventSourceResponse`, forwarding each event from the run's queue as an SSE frame (event name = the envelope's `type`, data = the JSON payload), and closes the stream after `done` or a fatal `error`
- [x] The events endpoint 403s a caller that does not own `run_id` (a different authenticated user's token), and 404s an unknown `run_id`
- [x] `POST /v1/query/{run_id}/stop` cancels the run's background task; calling it on an already-finished or already-stopped run returns `200` as a no-op, never an error (production-standards retry-safety gate)
- [x] The existing cost/operator_mode filtering (`filter_events_for_end_user`, the `OPERATOR_USER_IDS` allowlist) applies identically to the new streaming path: a non-operator caller's SSE stream never carries a `cost` event or an un-redacted `done.total_cost_usd`
- [x] The existing `POST /query` endpoint's behavior and tests are completely unaffected by this ticket

Breakdown:
- [x] `POST /v1/query`: run creation, 202 response
- [x] `GET /v1/query/{run_id}/events`: SSE streaming via `sse-starlette`, ownership check, cost filtering
- [x] `POST /v1/query/{run_id}/stop`: cancellation, idempotent
- [x] Tests: 202-before-completion timing, ownership 403, unknown-run 404, idempotent stop, cost filtering on the streaming path

Evidence (backfilled 2026-07-28 during phase close, from the judge review's independent verification, since this ticket's own evidence was never filled in when it was built and merged earlier in the same session):
- `python3 -m pytest tests/ -q`: 537 passed (whole-repo run, this ticket's suite included)
- `app.py:139-154` — `POST /v1/query`, 202, `run_id` plus `_STUB_PERSONA_NAME = "Assistant"` (`:119`), server-derived `user_id` at `:149`
- `app.py:177-215` — SSE via `EventSourceResponse`, event name = envelope `type`, closes on `done` (`:210`) or fatal `error` (`:212`)
- `app.py:157-174` — `_get_owned_run`, 404 before 403
- `app.py:222-234` — idempotent stop, always 200 once ownership is established
- Cost filtering on the streaming path: `app.py:207` calls `sanitize_event_for_end_user` unconditionally; tests at `test_streaming_endpoints.py:396`, `:407`, and `:422` (the third proves the real unfiltered run did produce a `cost` event, which is what makes the first two meaningful)
- `POST /query` unaffected: `test_streaming_endpoints.py:530` `class TestExistingQueryEndpointIsUnaffected`
- Commit 771e338 on `phase/1.2-react-shell-sse`

History:
- 2026-07-28 lead: created, scoped from Section 13.1's minimal subset
- 2026-07-28 lead: built, merged, tests passing (real-time work this session, evidence not filled in at the time)
- 2026-07-28 judge: independently re-verified against source and the real test run during the phase-level review; PASS
- 2026-07-28 lead: backfilled Evidence and set in-review from the judge's verified findings

### T-1.2-03: React app scaffold

Status: in-review
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
- [x] `npm install && npm run dev` starts a working Vite dev server with no errors
- [x] TypeScript strict mode is enabled (`tsconfig.json`); no `any` type anywhere without an explicit, commented justification (production-standards code-quality gate)
- [x] `HomePage` renders an empty state (`EmptyState`) with a `QueryInput`; submitting a non-empty query navigates to `ChatPage`
- [x] `ChatShell` holds the current run's state (a `run_id` once created, session state) as the page layout wrapper — corrected 2026-07-28 during phase close: the judge found `ChatShell.tsx` held a dead `useState` with no setter, never written to, and a stale docstring; T-1.2-08's actual wiring put run and token state in `App.tsx`/`ChatPage.tsx` instead, which has to reach `useAgentRun`/`createRun`/every chat component directly, so a layout-only wrapper had no reason to hold that state just to pass it through unused. Removed the dead state, the stale docstring, and the test that certified the dead attribute's absence as correct behavior (`ChatShell.tsx`, `ChatShell.test.tsx`), rather than record this criterion as met against code that did not do what it said
- [x] `QueryInput` has an explicit `<label>`, never a placeholder-only affordance (Section 12.10, success criterion 3.3.2), and is keyboard-operable (Tab, Enter submits)
- [x] Every new npm dependency added by this ticket passes `supply-chain-security.md`'s pre-install checks (no compromise reports, no unexplained postinstall script, `npm audit` clean) before being committed; document which packages were checked in the ticket's evidence

Breakdown:
- [x] Vite + React + TypeScript scaffold, strict mode, dev server
- [x] `HomePage`, `EmptyState`, `QueryInput`, `ChatShell`, `ChatPage` (routing between them)
- [x] `npm audit` and per-package supply-chain check for every new dependency

Evidence (backfilled 2026-07-28 during phase close, from the judge review's independent verification, since this ticket's own evidence was never filled in when it was built and merged earlier in the same session):
- `npm run test -- --run`: 120 tests passing (post-`ChatShell` cleanup); `npx tsc --noEmit`: clean
- `tsconfig.json` — `"strict": true` plus `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`; `grep -rn ': any\|as any\|<any>' frontend/src` returns zero hits
- `QueryInput.tsx:44` — real `<label htmlFor={inputId}>`; Enter handling at `:34-39`
- `npm audit`: 0 vulnerabilities
- `App.tsx:16-27` — minimal `useState`-based two-page routing, not `react-router-dom` (logged in `DECISIONS.md`)
- `ChatShell.tsx` cleaned up per the criterion-4 correction above; `git log --oneline -- frontend/src/components/chat/ChatShell.tsx` shows the phase-close fix as a separate commit from T-1.2-03's original build
- Commit 6b03433 on `phase/1.2-react-shell-sse` (original scaffold)

History:
- 2026-07-28 lead: created, scoped from Section 12.1/1.6
- 2026-07-28 lead: built, merged, tests passing (real-time work this session, evidence not filled in at the time)
- 2026-07-28 judge: independently re-verified against source and the real test run during the phase-level review; found criterion 4 false in the shipped system (`ChatShell.tsx`'s run-id state was dead code); PASS on every other criterion
- 2026-07-28 lead: fixed `ChatShell.tsx` and its test per the judge's finding, re-verified (120 tests passing, tsc clean), backfilled Evidence, set in-review

### T-1.2-04: Typed SSE consumption (`lib/events.ts`, `lib/api.ts`, `useAgentRun`)

Status: in-review
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
- [x] `lib/events.ts`'s `AgentEvent` union mirrors Section 2.3's payload shapes field-for-field for every type EXCEPT `cost` (which has no client-side variant at all, per Section 12.2's own note, since it is server-filtered before it ever reaches this client in the non-operator case this phase targets)
- [x] `lib/api.ts` provides typed wrappers: create a run (`POST /v1/query`), stop a run (`POST /v1/query/{run_id}/stop`)
- [x] `useAgentRun(runId)` opens one `EventSource` against `GET /v1/query/{run_id}/events`, registers a listener per known event type (matching Section 12.2's `knownTypes` list minus `cost`), and dispatches into a reducer/state array in arrival order — delivered via `fetch()` plus a hand-parsed `ReadableStream`, not the literal native `EventSource` API; see the deviation note below and the `DECISIONS.md` row logged for it
- [x] The hook closes its `EventSource` when `done` arrives, or when an `error` event with `fatal: true` arrives; it does NOT close on a non-fatal `error` (matching Section 12.2's `fatal`-only branching, never reading a nonexistent `code` or `recoverable` field)
- [x] The hook closes its `EventSource` on unmount (React cleanup), so navigating away from an active run does not leak an open connection
- [x] A real integration test (mocking `EventSource` or using a test server, builder's choice, documented) proves events dispatch in the order the server sent them, not just that individual handlers are wired

Deviation from criterion 3's literal wording, PASS on substance: Section 12.2's own snippet (`new EventSource(url, { withCredentials: true })`) assumes cookie-based session auth. This backend has no cookie session; every protected route requires a `Bearer` token in the `Authorization` header, and the native `EventSource` API cannot set custom request headers, so it cannot authenticate against this backend at all. `useAgentRun.ts:12-28` documents this in full; a `DECISIONS.md` row was added at phase close (it existed only in the source docstring until the judge review flagged that it was never logged as a decision).

Breakdown:
- [x] `lib/events.ts` typed union
- [x] `lib/api.ts` typed fetch wrappers
- [x] `useAgentRun.ts` hook: EventSource lifecycle, dispatch, fatal-close logic, unmount cleanup
- [x] Tests: union shape matches the real backend payloads (cross-check against a live or mocked `/events` response), ordering, fatal vs non-fatal close, unmount cleanup

Evidence (backfilled 2026-07-28 during phase close, from the judge review's independent verification, since this ticket's own evidence was never filled in when it was built and merged earlier in the same session):
- `npm run test -- --run` and `npx tsc --noEmit`: both clean as part of the whole-suite runs recorded on later tickets
- Union verified field-for-field against `src/system_03_search_agent/contracts/events.py` by the judge's own independent check: all 10 non-`cost` payload types plus the envelope match exactly (envelope `events.py:198-215` vs `events.ts:149-156`; `citation`'s 12 fields `events.py:118-134` vs `events.ts:107-120`); `cost` absent from the TS union at `events.ts:158-168`, `:177-188`, `:367-378`
- `lib/api.ts:93` `createRun`, `:118` `stopRun`, `:145` `openEventStream`
- Fatal-only close: `useAgentRun.ts:181-188` closes on `done` and on `error` with `payload.fatal === true` only; test at `useAgentRun.test.ts:214`
- Unmount cleanup: `useAgentRun.ts:340-343`; test at `useAgentRun.test.ts:235`
- Ordering tests at `useAgentRun.test.ts:115` and `:195`
- Commit 93dacfe on `phase/1.2-react-shell-sse`

History:
- 2026-07-28 lead: created, scoped from Section 12.2
- 2026-07-28 lead: built, merged, tests passing (real-time work this session, evidence not filled in at the time)
- 2026-07-28 judge: independently re-verified against source and the real test run during the phase-level review; PASS, flagged the `EventSource`-versus-`fetch` deviation as undocumented in `DECISIONS.md` (only in a source docstring)
- 2026-07-28 lead: logged the deviation to `DECISIONS.md`, backfilled Evidence, set in-review

### T-1.2-05: The streaming stepper and answer rendering

Status: in-review
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
- [x] `QueryPipelineStepper` renders `guard`, `think`, `plan`, `tool_start`, `tool_result` events as an ordered list of steps, each moving through pending, active, done/error states as events arrive; no `citation`-dependent rendering (out of scope this phase, per this file's Scope note)
- [x] `AnswerStream` renders each `token.payload.text` in arrival order; it does NOT attempt to render `CitationChip` markers this phase (no real citation data exists yet), but does not crash or drop text if a token carries `marker_ids` it cannot yet resolve — it renders the marker text plainly, deferring chip rendering to whichever phase builds `CitationChip` (2.2/3.4)
- [x] `GuardrailBanner` renders when `guard.passed` is `false`, choosing copy by `guard.category`, matching Section 12.6's table; no dollar figure, token count, or cost figure appears in any copy path (checked by grep, not just by reading the template, since the template has no interpolation slot for one)
- [x] `CapMessage` renders on a non-fatal cap-shaped `error` event (`fatal: false`), showing the partial-result-plus-explanation copy from Section 12.6, again with no dollar figure anywhere reachable
- [x] The streaming narrative region uses `aria-live="polite"`; `GuardrailBanner` and `CapMessage` use `role="alert"` (Section 12.10, success criterion 4.1.3)
- [x] `LoadingSkeleton` renders during the cold-start and guard-pending states (Section 12.5), never a blank pane

Breakdown:
- [x] `QueryPipelineStepper` with per-step pending/active/done/error states
- [x] `AnswerStream`, plain-text token rendering, no citation dependency
- [x] `GuardrailBanner`, `CapMessage`, both no-dollar-figure verified
- [x] `LoadingSkeleton`, cold-start and guard-pending states
- [x] Tests: step state transitions, token ordering, guardrail category copy, cap message copy, no-dollar-figure grep, aria-live/role=alert presence

Evidence:
- `npm run test -- --run` (independently re-run in `frontend/` after merge, not just the builder's own worktree report): 13 test files, 87 tests, all passing
- `npx tsc --noEmit` (independently re-run after merge): clean, no output
- Documented judgment call in `CapMessage.tsx`: the cap-shaped `error` trigger is `payload.fatal === false && /cap/i.test(payload.source)`, a substring match rather than a hardcoded `per_query_cost_cap` string, since Section 12.6 gives only one worked example and `system-design-patterns.md` pattern 4 names four distinct cap sources
- Commit df5a2a8 on `phase/1.2-react-shell-sse`, fast-forward merge from `worktree-agent-aab3a9b87327c122b`, no conflicts

History:
- 2026-07-28 lead: created, scoped from Section 12.3/12.5/12.6/12.10
- 2026-07-28 builder-aab3a9b: claimed, built all 5 components plus tests, reported done with self-verified evidence (87 tests passing, tsc clean)
- 2026-07-28 lead: merged into phase/1.2-react-shell-sse, independently re-ran test suite and tsc in the target checkout (both clean), set in-review pending judge close

### T-1.2-06: The stop button, wired end to end

Status: in-review
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: T-1.2-02, T-1.2-04, T-1.2-05
Spec: Technical_specification.md Section 12.3 (`StopButton`)

Files this ticket may create or modify:
- `frontend/src/components/chat/StopButton.tsx`
- `frontend/src/components/chat/StopButton.test.tsx` (new)

Acceptance criteria:
- [x] `StopButton` is enabled from the moment a `guard` event with `passed: true` arrives until `trust_signal`, `done`, or a fatal `error` arrives; disabled otherwise
- [x] Clicking it calls `POST /v1/query/{run_id}/stop` AND closes the local `EventSource` immediately, not waiting on the network round trip (Section 12.3's "feels instantly responsive" requirement) — a test with an artificially slow stop-endpoint response still shows the UI as stopped immediately
- [x] Clicking stop on an already-finished run is a no-op, matching the backend's idempotent 200 (no error toast, no crash)
- [x] Keyboard-operable: reachable by Tab, activatable by Enter and Space (Section 12.10, success criterion 2.1.1)
- [x] An end-to-end test (can be the Playwright test from T-1.2-07, cross-referenced here rather than duplicated) proves stopping a real, running query actually halts the server-side loop, not just the client-side UI state — delivered by T-1.2-07's second E2E test, which polls a server-side `/__e2e__/run_status` route asserting `RunEntry.task.cancelled()`, independent of the browser's own `AbortController`

Breakdown:
- [x] `StopButton` enabled/disabled state logic
- [x] Click handler: stop call plus immediate local `EventSource` close
- [x] Tests: enabled-window logic, immediate-UI-response under a slow backend, idempotent double-stop, keyboard operability

Evidence:
- `npm run test -- --run` (independently re-run in `frontend/` after merge): 14 test files, 106 tests, all passing (19 in `StopButton.test.tsx`)
- `npx tsc --noEmit` (independently re-run after merge): clean, no output
- `deriveStopEnabled` (`StopButton.tsx:48-60`): pure derivation from event existence, not array position, documented as correct because the agent loop can never emit a terminal event before guard passes
- Local `hasStopped` state (`StopButton.tsx:73`, reset on `runId` change) added because the events-only derivation could stay stuck enabled after a click, since this client stops listening the moment `stop()` runs; documented inline and logged to `DECISIONS.md`
- `stopRun` is called unawaited in the click handler (`StopButton.tsx:88-100`) so a slow backend never delays the local stopped state; failures are caught and logged via `console.warn(\`stopRun request failed for run ${runId}\`, caughtError)`. The caught `ApiError` is passed too, but its message is built at `api.ts:78` only from the HTTP status and the response body's `detail` field, never from a request header, so `token` cannot reach it either way (corrected 2026-07-28 per judge review; the original wording here said only `runId` is logged, which understated what the second `console.warn` argument actually carries, though the no-secrets property itself holds)
- Commit b635bc1 on `phase/1.2-react-shell-sse`, fast-forward merge from `worktree-agent-t1206`, no conflicts

History:
- 2026-07-28 lead: created, scoped from Section 12.3
- 2026-07-28 builder-t1206: claimed, built `StopButton` and its tests, reported done with self-verified evidence (106 tests passing, tsc clean)
- 2026-07-28 lead: merged into phase/1.2-react-shell-sse, independently re-ran test suite and tsc in the target checkout (both clean), set in-review pending judge close; acceptance criterion 5 (real E2E stop) left unchecked, deferred to T-1.2-07

### T-1.2-08: Wire ChatPage end to end, with minimal real auth

Status: in-review
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: T-1.2-02, T-1.2-04, T-1.2-05, T-1.2-06
Spec: Technical_specification.md Section 12.1 (component architecture, `ChatPage.tsx`: "Active or completed query view"), Section 25 line 3180 ("an empty chat endpoint wired end to end")

Added mid-phase, not part of the original 7-ticket decomposition. Gap found while scoping T-1.2-07: `ChatPage.tsx` is still T-1.2-03's placeholder (`git log`: "Streaming answer pipeline not wired up yet"), never calling `useAgentRun`/`createRun` and never rendering `QueryPipelineStepper`, `AnswerStream`, `GuardrailBanner`, `CapMessage`, `LoadingSkeleton`, or `StopButton`. No ticket among T-1.2-01 through T-1.2-07 named this wiring as its deliverable, even though the phase's own Section 25 line requires "an empty chat endpoint wired end to end" and `QueryPipelineStepper.tsx`'s own docstring (T-1.2-05) anticipated it explicitly: "so ChatPage (a later ticket's wiring) can pass one array to all of them." Separately, Section 12.2's `EventSource(url, { withCredentials: true })` snippet assumes cookie session auth; T-1.2-04 already documented why that does not hold for this Bearer-token backend, but nothing since has built any way for the frontend to acquire a token in the first place. No login/auth UI component is named anywhere in Section 12.1's component table, so this ticket's auth step has no spec name to adopt; it is scoped as the minimal real mechanism needed to make "wired end to end" true, not a finished auth UX.

Files this ticket may create or modify:
- `frontend/src/pages/ChatPage.tsx` (replace the placeholder body)
- `frontend/src/components/chat/ChatShell.tsx` (if it needs to hold run/token state, check its current shape first)
- A new minimal auth entry point, exact file left to the builder (e.g. `frontend/src/pages/HomePage.tsx` extended, or a small new `frontend/src/components/auth/AuthGate.tsx`), documented inline with the reasoning above
- `frontend/src/lib/api.ts` (if `/auth/login`/`/auth/signup` typed wrappers do not already exist; check before adding, this file already has `createRun`/`stopRun`/`openEventStream`)
- Corresponding `.test.tsx` files (new)

Acceptance criteria:
- [x] Submitting a query on `HomePage` leads to a `ChatPage` that actually calls `POST /v1/query` (via `lib/api.ts`'s `createRun`) and mounts `useAgentRun` against the returned `run_id`
- [x] `ChatPage` renders `LoadingSkeleton`, `QueryPipelineStepper`, `AnswerStream`, `GuardrailBanner`, `CapMessage`, and `StopButton` together, each driven by the same `events: AgentEvent[]` array from `useAgentRun`, matching the shared prop-shape convention `QueryPipelineStepper.tsx`'s docstring documents
- [x] A real bearer token is acquired through a real call to the existing `/auth/login` (and `/auth/signup` when no account exists yet) endpoints from build phase 1.1, not a hardcoded or fake string; held in memory only (component state), never written to `localStorage`/`sessionStorage`/a cookie, since this ticket does not own a token-persistence security decision
- [x] The full path is exercised by an integration-style test: render `App`, complete the minimal auth step, submit a query, and assert `createRun`/`openEventStream` were actually invoked with the acquired token (mocking `lib/api.ts` at the network boundary, matching this codebase's established test-mocking convention, not mocking `useAgentRun` itself)
- [x] No behavior from T-1.2-05 or T-1.2-06's already-merged components is altered, only wired in; their own test suites still pass unmodified

Breakdown:
- [x] Minimal real auth step: login (and signup-if-needed) against the real backend, in-memory token only
- [x] `ChatPage` wiring: `createRun` on submit, `useAgentRun` mount, all six components rendered from one shared `events` array
- [x] Tests: end-to-end render-and-submit integration test, auth step unit tests

Evidence:
- `npm run test -- --run` (independently re-run in `frontend/` after merge): 15 test files, 121 tests, all passing (106 pre-existing plus 15 new: 6 `AuthGate`, 7 `ChatPage`, 2 `App`)
- `npx tsc --noEmit` (independently re-run after merge): clean, no output
- `AuthGate.tsx`: two explicit actions ("Log in", "Sign up") rather than try-login-then-fall-back-to-signup, because `auth/router.py`'s `login` endpoint returns an identical 401 and identical "invalid email or password" detail for both an unknown email and a wrong password (deliberate anti-enumeration behavior, confirmed by reading the router); documented inline and in `DECISIONS.md`
- `ChatPage.tsx:34-122`: `createRun` called on mount with a per-mount `crypto.randomUUID()` session id, `useAgentRun(runId, token)` mounted unconditionally (treats `runId: null` as idle per that hook's own contract), all six components rendered from the one shared `events` array, a `runFailedBeforeGuard` branch surfaces a stream-open failure that arrives before any `guard` event instead of hanging on the loading skeleton forever
- Token held in `App.tsx:26` component state only, never `localStorage`/`sessionStorage`/a cookie; never logged, `AuthGate.tsx` logs HTTP status only on failure, matching `StopButton.tsx`'s own `console.warn` convention
- No merged T-1.2-05/06 component `.tsx` source was touched (`git diff --stat` against the pre-merge tree confirms only `ChatPage.tsx`, `ChatPage.test.tsx`, `App.tsx`, `App.test.tsx`, `lib/api.ts`, and the new `components/auth/` were touched); their own test files pass unmodified
- Commit 50fcb01 on `phase/1.2-react-shell-sse`, merge from `worktree-agent-t1207` with one resolved conflict in `DECISIONS.md` (two independent appends from a common ancestor, no content conflict)

History:
- 2026-07-28 lead: created mid-phase during T-1.2-07 dispatch prep, closing a decomposition gap in the original 7-ticket scoping (see the note above); logged to DECISIONS.md
- 2026-07-28 builder-t1207: claimed, built `AuthGate`, wired `ChatPage`/`App`, reported done with self-verified evidence (121 tests passing, tsc clean)
- 2026-07-28 lead: merged into phase/1.2-react-shell-sse (one resolved DECISIONS.md conflict, no content conflict), independently re-ran test suite and tsc in the target checkout (both clean), set in-review pending judge close
- 2026-07-28 lead: background security review flagged a weak-credentials hint in the signup-failure copy ("password may be too short", implying a policy the backend does not enforce, `min_length=1`); fixed directly (commit 40970a6), 121 tests still passing

### T-1.2-07: Playwright install and the first real E2E test

Status: in-review
Refine: refined
Branch: phase/1.2-react-shell-sse
Depends on: T-1.2-01, T-1.2-02, T-1.2-03, T-1.2-04, T-1.2-05, T-1.2-06, T-1.2-08
Spec: Technical_specification.md Section 23 (testing strategy, browser-driven E2E); `tracker/BOARD.md`'s "Playwright not installed" flag; `.claude/rules/supply-chain-security.md`

Files this ticket may create or modify:
- `frontend/package.json` (add `@playwright/test` as a devDependency)
- `frontend/playwright.config.ts`
- `frontend/e2e/query-stream-and-stop.spec.ts` (new)

Acceptance criteria:
- [x] `@playwright/test` is installed pinned to the exact version verified clean this session (`1.62.0`, or a later version re-verified the same way at install time per `supply-chain-security.md`, never `@latest`, never any `playwright-1.4x`-shaped impostor package name)
- [x] `npx playwright install` (browser binaries) runs cleanly in this environment
- [x] One real E2E test drives a real browser against the real running frontend AND the real backend (with `litellm` mocked at the backend, same pattern every other test in this repo uses, no real API key needed): types a query, submits it, observes the pipeline stepper progress, observes the answer stream render tokens, and reaches a terminal `done` state. Caveat: as of build phase 2.0, `write_node`'s only real code path that emits a `token` event is the per-query-cap-exceeded partial result (real citation-grounded synthesis is phase 2.2's job), so this test drives that real path via a deliberately low `PER_QUERY_COST_CAP_USD=0.02`, not a "normal" success path that does not yet exist to test
- [x] A second E2E test proves the stop button: starts a query, clicks stop mid-stream, and asserts the run actually halts (no further token events arrive after the stop click, matching T-1.2-06's server-side halt requirement). Proven server-side via a throwaway `/__e2e__/run_status` introspection route polling `RunEntry.task.cancelled()`, not just a client-side absence-of-events check
- [x] `axe-core` (or an equivalent automated accessibility scanner) runs against the rendered `ChatPage` as part of this test suite, per Section 12.10's "automated axe-core check in CI as a baseline". Scoped to WCAG 2.1 A/AA tags; two pre-existing best-practice-only findings (`landmark-one-main`, `page-has-heading-one`) are flagged, not fixed, since fixing them touches already-merged `HomePage.tsx`/`ChatShell.tsx`, outside this ticket's file scope

Breakdown:
- [x] Pinned `@playwright/test` install, browser binaries, re-verified against `supply-chain-security.md` at install time (not just at this session's precheck)
- [x] `playwright.config.ts`: base URL, dev-server startup (`webServer` config launching both the FastAPI backend with mocked LiteLLM and the Vite dev server)
- [x] E2E test: full query-to-done flow
- [x] E2E test: stop mid-stream actually halts the server
- [x] `axe-core` automated accessibility scan wired into the same suite

Evidence:
- `npx playwright test` (independently re-run in `frontend/` after merge, browser binaries reinstalled fresh in this checkout, real PostgreSQL `search_agent_users` confirmed reachable first): 3 passed, ~14s
- `npm run test -- --run` (independently re-run after merge): 15 test files, 121 tests, all passing, unaffected
- `npx tsc --noEmit` (independently re-run after merge): clean, no output
- `python3 -m pytest tests/ -q` (independently re-run after merge, regression check on the Python side): 537 passed, unaffected
- Fresh supply-chain re-verification, run at actual install time, not reused from the earlier session precheck: `@playwright/test`/`playwright`/`playwright-core`@1.62.0, `@axe-core/playwright`@4.12.1, `@types/node`@26.1.2, all GitHub Actions OIDC trusted-published or a recognized DefinitelyTyped/Deque bot, no postinstall/preinstall scripts, no compromise reports; all five pinned exact in `package.json`
- `tests/e2e_support/mock_llm_backend.py`: monkeypatches `litellm.acompletion`/`get_model_info` once at process start (the in-process `monkeypatch` technique every other test uses cannot reach a separate `webServer` process), runs the real, unmodified FastAPI `app`; extends it at runtime with a loopback-only CORS middleware and the read-only `/__e2e__/run_status` route, never edits `app.py`
- Commit 12b7829 on `phase/1.2-react-shell-sse`, merged cleanly (no conflicts) from `worktree-agent-t1207b`

History:
- 2026-07-28 lead: created, scoped from Section 23 and the standing Playwright board flag
- 2026-07-28 lead: dispatched only after independently re-verifying the Playwright supply-chain check myself first (the product owner's explicit zero-doubt instruction), and after adding T-1.2-08 as a dependency once ChatPage's placeholder state was discovered
- 2026-07-28 builder-t1207b: claimed, ran a fresh supply-chain re-verification before installing (matched the precheck), built the mock-LLM E2E backend entrypoint and three E2E tests, reported done with self-verified evidence (121 unit tests unaffected, tsc clean, 3 E2E tests passing, 537 Python tests unaffected)
- 2026-07-28 lead: merged into phase/1.2-react-shell-sse, independently re-ran the full verification chain (unit tests, tsc, a fresh `npx playwright install` plus `npx playwright test`, and the Python suite) in the target checkout, all clean; gitignored `frontend/test-results/`/`frontend/playwright-report/`; set in-review pending judge close

## Findings

Filed by the adversary after the judge passed all 8 tickets, against the real running system (real PostgreSQL, real backend with only the LLM call mocked, real Chromium via Playwright). No critical or high findings; zero 5xx across every hostile input tried, no access-control bypass, no XSS that executed. Six findings, all medium or below.

### F-1.2-01: the run registry never evicts a completed or abandoned run

Severity: medium. Status: confirmed
Raised by: adversary (independently corroborated by the judge's own source review)
Ticket: none this phase, deferred

What happened: `RunRegistry._runs` has no `del`, `pop`, `clear`, or TTL anywhere in `core/run_registry.py`. 400 runs were created by one authenticated account in 32 seconds with zero rejections and no rate limit; every `RunEntry` (its queue, all buffered events, and its finished `Task`) is retained for the process lifetime. Distinct from the already-tracked daily-cap gap (F-2.0-04, phase 4.6): that caps spend, it does not reclaim memory.

History:
- 2026-07-28 adversary: filed, reproduced with a 400-run creation loop against the real backend
- 2026-07-28 judge: independently found the same gap during the phase-level premise review (`run_registry.py:152`), calling it "not a phase-1.2 defect... phase 4.0 must close it before this is a public surface"
- 2026-07-28 lead: confirmed both independent findings agree; deferred to build phase 4.0 ("REST plus SSE adapter finalized as the public API surface"), the phase whose own Section 25 line makes this system a public surface for the first time. Tracked as an open flag on `tracker/BOARD.md`

### F-1.2-02: an abandoned client connection does not halt the server-side run, and React StrictMode doubles run creation in dev

Severity: medium. Status: confirmed
Raised by: adversary
Ticket: none this phase, deferred

What happened: a client that aborts its SSE stream after one event does not cancel the server-side task; the run executes all four LLM calls to completion regardless (`task_cancelled` stays `false` throughout, verified via `/__e2e__/run_status`). Separately, `<StrictMode>`'s dev-mode double-invoke of `ChatPage`'s mount effect (already known from `DECISIONS.md` row 172, T-1.2-07) means one real user submit creates two real backend runs; only one is ever consumed by the UI, and the abandoned one runs to completion and is retained forever per F-1.2-01. Compounds F-1.2-01 directly: every dev-mode query currently costs two runs, one of them permanently orphaned.

History:
- 2026-07-28 adversary: filed, reproduced via a real client abort and via observing two `POST /v1/query` calls from one submit
- 2026-07-28 lead: confirmed. The phase's own Scope note already frames this phase as "the minimal REAL version" of Section 13.1, explicitly deferring "the finalized [...] shape" to build phase 4.0; auto-cancellation on client disconnect is part of that finalization, not a phase-1.2 gap in isolation. Deferred to build phase 4.0 alongside F-1.2-01. Tracked as an open flag on `tracker/BOARD.md`

### F-1.2-03: a second concurrent SSE consumer for the same run silently receives zero events, HTTP 200

Severity: medium. Status: confirmed
Raised by: adversary
Ticket: none this phase, deferred

What happened: the per-run `asyncio.Queue` is destructively single-consumer. When two authenticated, owning clients race to open `GET /v1/query/{run_id}/events` for the same run, whichever loses the race gets zero events, a clean 200, and a clean close, with no error signal. A reconnect after the first connection already drained the queue behaves identically: a legitimate client cannot distinguish "you missed everything" from "the run produced nothing," because both look like an empty successful stream. This is the resumability gap the phase's own Scope note already names as deferred (`Last-Event-ID`, explicitly out of scope, build phase 4.0's job), reproduced concretely rather than only stated as a known gap.

History:
- 2026-07-28 adversary: filed, reproduced across 3 trials with two real concurrent SSE clients, nondeterministic winner each time
- 2026-07-28 lead: confirmed as the concrete, reproducible shape of the already-named resumability deferral. Deferred to build phase 4.0 alongside F-1.2-01/02. Tracked as an open flag on `tracker/BOARD.md`

### F-1.2-04: signup's 409 response undermines login's own documented anti-enumeration guarantee

Severity: low-medium. Status: confirmed
Raised by: adversary
Ticket: none this phase, needs a product decision

What happened: `POST /auth/login` genuinely returns an identical status and byte-identical body for a wrong password versus a nonexistent email (verified directly, not just trusted from `DECISIONS.md` row 165's claim; median response time also showed no distinguishing signal, 41.1ms vs 42.3ms). The sibling endpoint gives the same fact away for free: `POST /auth/signup` with an already-registered email returns `409 {"detail":"email already registered"}`. `AuthGate.tsx`'s own UI puts "Sign up" directly next to "Log in" (the T-1.2-08 anti-enumeration design decision), so the oracle login deliberately withholds is one click away on the same screen. This is a phase 1.1 backend behavior (the `409` response), surfaced and made concretely exploitable by phase 1.2's own UI choice.

History:
- 2026-07-28 adversary: filed, reproduced via direct `curl` against `/auth/signup`
- 2026-07-28 lead: confirmed the behavior. Not fixed in this phase: closing it is a real product trade-off (an ambiguous or verification-gated signup response changes the signup UX, not a pure bug fix), not a mechanical patch. Tracked as an open flag on `tracker/BOARD.md`, trigger is build phase 6.1's full `dev-standards` hardening pass and security scan, or an earlier explicit product-owner decision if the exposure is judged urgent before then

### F-1.2-05: `CreateRunRequest.text` accepted an empty or whitespace-only query, burning a full pipeline run

Severity: low. Status: closed
Raised by: adversary
Ticket: none needed, fixed directly (in scope, trivial)

What happened: `text: str = Field(..., max_length=2000)` had no minimum. `{"text": ""}` and `{"text": "   \t\n  "}` both returned 202 and ran all four LLM calls (guard, think, plan, write) for no real query.

Fix: `app.py`'s `CreateRunRequest` gained `min_length=1` plus a `field_validator` rejecting a stripped-empty string (`min_length=1` alone still accepts whitespace-only). Two new tests: `test_empty_text_returns_422`, `test_whitespace_only_text_returns_422`. 539 tests passing, up from 537.

History:
- 2026-07-28 adversary: filed, reproduced via direct `curl` with empty and whitespace-only `text`
- 2026-07-28 lead: fixed directly, in scope for this phase (the request model T-1.2-02 owns), re-verified (539 tests passing)

### F-1.2-06: `run_id` existence is distinguishable (404 vs 403) to an authenticated caller

Severity: informational. Status: rejected
Raised by: adversary
Ticket: none, not a defect

What happened: an authenticated caller can tell an unowned-but-existing `run_id` (403) apart from a nonexistent one (404).

History:
- 2026-07-28 adversary: filed as informational, explicitly noting it is "impractical to exploit" given uuid4 run ids and that it matches the ticket's own stated acceptance criterion (404 before 403, an explicit T-1.2-02 requirement)
- 2026-07-28 lead: rejected as a finding. This is documented, spec-required behavior (`tracker/phase_1.2.md`'s T-1.2-02 acceptance criteria), not a defect; the adversary itself did not claim otherwise

## History

- 2026-07-28 lead: phase opened, dependency verified against Section 25 and `tracker/BOARD.md`, product_refine cleared by product-owner decision, LEARNINGS.md read filtered to this phase, decomposed into 7 tickets (T-1.2-01 through T-1.2-07), all refined at creation. Scope explicitly bounded against the full Section 13.1 API (deferred to phase 4.0) and against Section 12 components whose backing data does not exist until later phases (citations, persona, feedback), confirmed with the product owner before dispatch.
