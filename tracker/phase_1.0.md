# Phase 1.0: FastAPI skeleton

Branch: `phase/1.0-fastapi-skeleton`
Depends on: none
Delivers (Technical_specification.md Section 25): FastAPI app skeleton, health endpoint, the core `run(query, context)` contract stub with the v1 event taxonomy typed (Decision A), Pydantic boundary validation.

Dependency check at open: no dependency phases exist for 1.0, so this phase can start immediately. Confirmed against Section 25's build order table (line 3178) and the dependency graph (lines 3223 to 3291), where `1.0` has no incoming edge.

LEARNINGS.md filtered to this phase: no entries are scoped to phase 1.0 or its tools specifically. Standing lessons that still apply while working this phase: use the Edit tool for structured files, never `sed` or a heredoc, since PostToolUse hooks (including `sync-board.sh` for this file) only fire on Edit and Write; verify `.claude/` tracked status with `git check-ignore -v` rather than trusting `git status` if anything looks silently unwritten; keep bulk edits away from `DECISIONS.md`.

## Tickets

### T-1.0-01: Event contract and request models

Status: in-review
Refine: refined
Branch: phase/1.0-fastapi-skeleton
Depends on: none
Spec: Technical_specification.md Section 2.1 (lines 217-248), Section 2.2 (lines 250-272), Section 2.3 (lines 274-371)

Files this ticket may create or modify:
- `src/system_03_search_agent/contracts/__init__.py`
- `src/system_03_search_agent/contracts/query.py`
- `src/system_03_search_agent/contracts/events.py`
- `tests/system_03_search_agent/contracts/test_query.py`
- `tests/system_03_search_agent/contracts/test_events.py`

Acceptance criteria:
- [ ] `Query(text=...)` rejects a `text` value over 2000 characters, a `session_id` or `trace_id` over 64 characters, and a `user_id` over 64 characters, each with a validation error, never a silent truncation
- [ ] Constructing a `Query` with no `text` field raises a validation error; constructing one with only `text`, `session_id`, and `trace_id` succeeds with `user_id` defaulting to `None` and `audience_depth` defaulting to `"researcher"`
- [ ] `RequestContext.surface` accepts only `web_ui`, `rest_sse`, `mcp`, or `cli` and rejects any other string
- [ ] The `Event` envelope model requires `type`, `version`, `trace_id`, `seq`, `ts`, and `payload`; omitting any one of these raises a validation error
- [ ] `Event.type` accepts only the eleven taxonomy values (`guard`, `think`, `plan`, `tool_start`, `tool_result`, `token`, `citation`, `trust_signal`, `cost`, `error`, `done`) and rejects any other string
- [ ] `Event.version` is fixed to the literal `"v1"` and rejects any other value
- [ ] Every payload model declares `max_length` on its string fields and `max_items` on its array fields matching Section 2.3's values (`think.narrative` 500, `think.resolved_entities` 20, `plan.narrative` 500, `plan.tool_calls` 20 with `tool` an enum pinned to the seven registered tool names, `tool_result.summary` 1000, `error.scope` 16, `error.source` 64, `error.error_class` 16, `error.message` 256)

Breakdown:
- [ ] `Query` and `RequestContext` models
- [ ] `Event` envelope model
- [ ] Per-type payload models (guard, think, plan, tool_start, tool_result, token, citation, trust_signal, cost, error, done)
- [ ] Tests: valid input, invalid input, missing/null input for each model above

Evidence:
- (filled at close: command output, file:line, test result)

History:
- 2026-07-27 lead: created, scoped from Section 2.1-2.3, phase 1.0 open
- 2026-07-27 lead: reviewed with product owner, no blocking feedback, refined
- 2026-07-27 builder-events-models: claimed, built in worktree agent-a97ddd816d5a2984b
- 2026-07-27 builder-events-models: finished, 143 passed, clean compile, commit 5c6bfd5, merged into phase branch, in-review, awaiting judge

### T-1.0-02: FastAPI app skeleton and health endpoint

Status: in-review
Refine: refined
Branch: phase/1.0-fastapi-skeleton
Depends on: none
Spec: Technical_specification.md Section 25 row 1.0 (line 3178), Section 1.6 (lines 193-209)

Files this ticket may create or modify:
- `src/system_03_search_agent/adapters/__init__.py`
- `src/system_03_search_agent/adapters/web_sse/__init__.py`
- `src/system_03_search_agent/adapters/web_sse/app.py`
- `tests/system_03_search_agent/adapters/web_sse/test_health.py`

Acceptance criteria:
- [ ] `GET /health` returns HTTP 200 with a JSON body when the app is running, and requires no authentication
- [ ] The FastAPI app imports and boots cleanly under uvicorn with zero import errors, verified by a successful test-client startup
- [ ] The app lives under `adapters/web_sse/` per Section 1.6's target module layout, not mixed into `core/` or `contracts/`

Breakdown:
- [ ] FastAPI app instance and router wiring
- [ ] `/health` endpoint
- [ ] Test-client startup test

Evidence:
- (filled at close: command output, file:line, test result)

History:
- 2026-07-27 lead: created, scoped from Section 25 row 1.0 and Section 1.6, phase 1.0 open
- 2026-07-27 lead: reviewed with product owner, health-endpoint scope (bare liveness check, not a dependency check) confirmed as-is, no blocking feedback, refined
- 2026-07-27 builder-fastapi-skeleton: claimed, built in worktree agent-a900df30addfbeecd
- 2026-07-27 builder-fastapi-skeleton: correctly flagged a broken shared venv (its diagnosis held up under lead re-verification) and a repo-wide pytest sys.path gap; finished after both were fixed, 3 passed, clean compile, commit a971d428, merged into phase branch, in-review, awaiting judge

### T-1.0-03: run() contract stub wired to the FastAPI boundary

Status: in-review
Refine: refined
Branch: phase/1.0-fastapi-skeleton
Depends on: T-1.0-01, T-1.0-02
Spec: Technical_specification.md Section 2.1 (lines 217-230), Section 1.4-1.5 (lines 179-191)

Files this ticket may create or modify:
- `src/system_03_search_agent/core/__init__.py`
- `src/system_03_search_agent/core/run.py`
- `src/system_03_search_agent/adapters/web_sse/app.py` (wiring only, endpoint added)
- `tests/system_03_search_agent/core/test_run.py`
- `tests/system_03_search_agent/adapters/web_sse/test_query_endpoint.py`

Acceptance criteria:
- [ ] `run(query: Query, context: RequestContext)` is declared as `AsyncIterator[Event]`, and every item it yields is an instance of the `Event` model from T-1.0-01, never a bare string or dict
- [ ] Calling `run()` with a valid stub `Query` yields at least one `guard` event and terminates with exactly one `done` event, both schema-valid against the `Event` envelope
- [ ] The FastAPI query endpoint validates every request against the `Query` and `RequestContext` Pydantic models at the boundary; posting a body missing a required `Query` field returns HTTP 422, never a 500 or a silent default
- [ ] Posting a `Query.text` value over 2000 characters to the endpoint returns a validation error response and never reaches `run()`
- [ ] The stub `run()` makes no direct LLM call and no direct tool call; it is a typed scaffold only, deferring the real Guardrail-Think-Plan-Act-Write loop to build phase 2.0

Breakdown:
- [ ] `run()` stub implementation
- [ ] Query endpoint wiring in `app.py`
- [ ] Tests: valid input, invalid input, missing/null input on the query endpoint; stub-yield shape test on `run()`

Evidence:
- (filled at close: command output, file:line, test result)

History:
- 2026-07-27 lead: created, scoped from Section 2.1 and Section 1.4-1.5, phase 1.0 open, depends on T-1.0-01 and T-1.0-02
- 2026-07-27 lead: reviewed with product owner, stub scope (guard + done only, not all eleven event types) confirmed as-is, no blocking feedback, refined
- 2026-07-27 builder-run-stub: claimed, built directly on phase branch (sole active builder, no worktree needed)
- 2026-07-27 builder-run-stub: finished, 173 passed (full suite), clean compile, ruff clean, commit cf630a9, in-review, awaiting judge

## Findings

No findings filed yet. The adversary pass runs at stage 8 of the build cadence, after the judge has certified tickets in this phase.
