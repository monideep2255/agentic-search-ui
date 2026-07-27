# Phase 1.0: FastAPI skeleton

Branch: `phase/1.0-fastapi-skeleton`
Depends on: none
Delivers (Technical_specification.md Section 25): FastAPI app skeleton, health endpoint, the core `run(query, context)` contract stub with the v1 event taxonomy typed (Decision A), Pydantic boundary validation.

Dependency check at open: no dependency phases exist for 1.0, so this phase can start immediately. Confirmed against Section 25's build order table (line 3178) and the dependency graph (lines 3223 to 3291), where `1.0` has no incoming edge.

LEARNINGS.md filtered to this phase: no entries are scoped to phase 1.0 or its tools specifically. Standing lessons that still apply while working this phase: use the Edit tool for structured files, never `sed` or a heredoc, since PostToolUse hooks (including `sync-board.sh` for this file) only fire on Edit and Write; verify `.claude/` tracked status with `git check-ignore -v` rather than trusting `git status` if anything looks silently unwritten; keep bulk edits away from `DECISIONS.md`.

## Tickets

### T-1.0-01: Event contract and request models

Status: rejected
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
- [x] `Query(text=...)` rejects a `text` value over 2000 characters, a `session_id` or `trace_id` over 64 characters, and a `user_id` over 64 characters, each with a validation error, never a silent truncation
- [x] Constructing a `Query` with no `text` field raises a validation error; constructing one with only `text`, `session_id`, and `trace_id` succeeds with `user_id` defaulting to `None` and `audience_depth` defaulting to `"researcher"`
- [x] `RequestContext.surface` accepts only `web_ui`, `rest_sse`, `mcp`, or `cli` and rejects any other string
- [x] The `Event` envelope model requires `type`, `version`, `trace_id`, `seq`, `ts`, and `payload`; omitting any one of these raises a validation error
- [x] `Event.type` accepts only the eleven taxonomy values (`guard`, `think`, `plan`, `tool_start`, `tool_result`, `token`, `citation`, `trust_signal`, `cost`, `error`, `done`) and rejects any other string
- [x] `Event.version` is fixed to the literal `"v1"` and rejects any other value
- [x] Every payload model declares `max_length` on its string fields and `max_items` on its array fields matching Section 2.3's values (`think.narrative` 500, `think.resolved_entities` 20, `plan.narrative` 500, `plan.tool_calls` 20 with `tool` an enum pinned to the seven registered tool names, `tool_result.summary` 1000, `error.scope` 16, `error.source` 64, `error.error_class` 16, `error.message` 256)

Breakdown:
- [x] `Query` and `RequestContext` models
- [x] `Event` envelope model
- [x] Per-type payload models (guard, think, plan, tool_start, tool_result, token, citation, trust_signal, cost, error, done)
- [x] Tests: valid input, invalid input, missing/null input for each model above

Evidence:
- Test suite, judge-run, not builder-reported: `source venv/bin/activate && python -m pytest tests/ -q` returned `173 passed, 1 warning in 0.26s`. Contracts subset `python -m pytest tests/system_03_search_agent/contracts -q` returned `143 passed in 0.07s` (117 in `test_events.py`, 26 in `test_query.py`).
- Compile: `python -m py_compile src/system_03_search_agent/contracts/query.py src/system_03_search_agent/contracts/events.py src/system_03_search_agent/adapters/web_sse/app.py src/system_03_search_agent/core/run.py` exited 0.
- AC1: `query.py:15-18` declares `max_length` 2000 on `text`, 64 on `session_id`, `trace_id`, and `user_id`. `test_query.py:43-45, 51-53, 59-61, 68-70` assert `ValidationError` one character over each; `test_query.py:72-75` asserts a 2500-character `text` raises rather than truncating.
- AC2: `query.py:15-21`, all three ids required, `user_id` defaults `None`, `audience_depth` defaults `"researcher"`. `test_query.py:20-22` (missing `text` raises), `test_query.py:32-35` (minimal construction, both defaults asserted).
- AC3: `query.py:27` is `Literal["web_ui", "rest_sse", "mcp", "cli"]`. `test_query.py:98-105` parametrizes all four and asserts `desktop_app` rejected.
- AC4: `events.py:178-195` declares all six fields, none optional. `test_events.py:54-61` parametrizes deletion of each of the six and asserts `ValidationError`.
- AC5: `events.py:178-190` is a `Literal` of exactly the eleven values. `test_events.py:70-77` parametrizes all eleven plus an unknown-value rejection; `test_events.py:79-80` pins the count at 11.
- AC6: `events.py:191` is `Literal["v1"]`. `test_events.py:83-90` asserts `v1` accepted, `v2` rejected.
- AC7: all eleven payload models verified field by field against Section 2.3. Spec-numbered values match exactly: `ThinkPayload.narrative` 500 (`events.py:71`), `resolved_entities` 20 (`events.py:75`), `PlanPayload.narrative` 500 (`events.py:90`), `tool_calls` 20 (`events.py:91`), `ToolCall.tool` pinned to the seven-name `ToolName` literal (`events.py:27-35, 82`), `ToolResultPayload.summary` 1000 (`events.py:104`), `ErrorPayload.scope` 16, `source` 64, `error_class` 16, `message` 256 (`events.py:157-162`). Unnumbered string fields carry conservative caps per the multi-agent gate. `CitationPayload.source_url` is host-pinned at `events.py:47, 123-125`, proven by `test_events.py:394-405`.
- Gate result, type hints: pass. Every field on all fifteen models in `query.py` and `events.py` is annotated.
- Gate result, snake_case: pass. No camelCase field or argument in either module.
- Gate result, secrets: pass. `grep -rniE "(api[_-]?key|secret|password|token|dsn|connection[_-]?string)\s*=\s*[\"']" src tests` returned no matches.
- Gate result, v1 scope boundary: pass. The only `blast` occurrence in the branch is `test_events.py:253`, a negative test asserting `ToolCall(tool="blast_search", ...)` is rejected by the seven-tool enum. That enforces the boundary rather than crossing it.
- Gate result, explicit-schema constraint (`ai-security-standards`, and the multi-agent pipeline gate in `production-standards`): FAIL. `events.py:195` types the envelope's payload as `payload: dict[str, Any]`, an open dict. Judge probe, `PYTHONPATH=src python`: `Event(type="guard", version="v1", trace_id="t", seq=0, ts=..., payload={"totally": "unknown", "blob": "x"*200000, "nested": {...}})` was accepted, printing `PROBE1 open-dict payload accepted, keys= ['totally', 'blob', 'nested'] blob_len= 200000`. A second probe accepted `type="done"` carrying a `guard` payload: `PROBE2 type=done carrying a guard payload accepted: done {'passed': True, 'category': 'ok'}`. The eleven typed payload models are therefore never enforced on any event the system actually emits, and the `max_length` and `max_items` caps verified under AC7 do not bind the blast radius of a real payload.
- Gate result, bounded inputs at the HTTP boundary: FAIL. `query.py:29` types `session_memory` as `Any | None`. Judge probe against the live app: `POST /query` with `context.session_memory` set to a 500,000-character nested object returned `HTTP 200`, printing `HTTP boundary accepted 500KB arbitrary session_memory -> 200`.
- Why the documented deferral does not hold: `events.py:9-11` defers the discriminated union to "a later ticket that builds the Guardrail-to-Write pipeline these events flow through". T-1.0-03 (commit cf630a9) built that pipeline inside this same phase. `core/run.py:33, 50` emit `payload=<model>.model_dump()`, and `adapters/web_sse/app.py:33-35` serializes the result through `response_model=list[Event]`, so unvalidated envelopes already leave the process over HTTP today. The premise the deferral rested on was falsified before the ticket reached review.

History:
- 2026-07-27 lead: created, scoped from Section 2.1-2.3, phase 1.0 open
- 2026-07-27 lead: reviewed with product owner, no blocking feedback, refined
- 2026-07-27 builder-events-models: claimed, built in worktree agent-a97ddd816d5a2984b
- 2026-07-27 builder-events-models: finished, 143 passed, clean compile, commit 5c6bfd5, merged into phase branch, in-review, awaiting judge
- 2026-07-27 judge: rejected, all seven acceptance criteria pass and 143 contract tests are green, but `Event.payload` is an open `dict[str, Any]` (events.py:195) so the eleven typed payload models never bind any emitted event, which fails the explicit-schema gate in `ai-security-standards` and the multi-agent pipeline gate in `production-standards`; see F-1.0-01 and F-1.0-02

### T-1.0-02: FastAPI app skeleton and health endpoint

Status: done
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
- [x] `GET /health` returns HTTP 200 with a JSON body when the app is running, and requires no authentication
- [x] The FastAPI app imports and boots cleanly under uvicorn with zero import errors, verified by a successful test-client startup
- [x] The app lives under `adapters/web_sse/` per Section 1.6's target module layout, not mixed into `core/` or `contracts/`

Breakdown:
- [x] FastAPI app instance and router wiring
- [x] `/health` endpoint
- [x] Test-client startup test

Evidence:
- Test suite, judge-run: `source venv/bin/activate && python -m pytest tests/ -q` returned `173 passed, 1 warning in 0.26s`. Adapter subset `python -m pytest tests/system_03_search_agent/adapters -q` returned `18 passed, 1 warning in 0.12s` (3 in `test_health.py`, 15 in `test_query_endpoint.py`).
- Compile: `python -m py_compile` over the four phase modules exited 0.
- AC1: `app.py:17-19` declares `@app.get("/health", response_model=HealthResponse)` returning `HealthResponse(status="ok")`, with no dependency, no security scheme, and no auth middleware anywhere in the module. `test_health.py:8-11` asserts HTTP 200, `test_health.py:14-17` asserts the JSON body is exactly `{"status": "ok"}`, `test_health.py:20-23` asserts the status code is neither 401 nor 403.
- AC2: every one of the 18 adapter tests constructs `TestClient(app)` and issues a request, which exercises the full import and app-startup path. All 18 pass, so the module imports and the ASGI app instantiates with zero import errors.
- AC3: the file is at `src/system_03_search_agent/adapters/web_sse/app.py`, matching Section 1.6's `adapters/web_sse/  # FastAPI + SSE` line (Technical_specification.md:204). `git diff --stat main..HEAD` confirms nothing was added under `core/` or `contracts/` by this ticket's commit a971d42.
- Gate result, type hints: pass. `app.py:18` is `def get_health() -> HealthResponse`, fully annotated, and `HealthResponse.status: str` is annotated at `app.py:14`.
- Gate result, snake_case: pass.
- Gate result, endpoint tests for valid, invalid, and missing input: pass with one not-applicable. `/health` is a `GET` with no path parameter, no query parameter, and no body, so it has no invalid-input or missing-input surface to exercise. The three valid-path tests are the complete testable set for this endpoint.
- Gate result, secrets: pass. No credential literal added; the `grep` over `src` and `tests` returned no matches.
- Gate result, v1 scope boundary: pass. A health endpoint and an app instance only, no compute tool and nothing on the PRD out-of-scope list.
- Advisory, not blocking: `HealthResponse.status` is a bare `str` with no `max_length` (`app.py:14`). It is server-authored and outbound-only, never populated from untrusted input, so the multi-agent gate's blast-radius rationale does not bite. `Literal["ok"]` would be the tighter declaration.

History:
- 2026-07-27 lead: created, scoped from Section 25 row 1.0 and Section 1.6, phase 1.0 open
- 2026-07-27 lead: reviewed with product owner, health-endpoint scope (bare liveness check, not a dependency check) confirmed as-is, no blocking feedback, refined
- 2026-07-27 builder-fastapi-skeleton: claimed, built in worktree agent-a900df30addfbeecd
- 2026-07-27 builder-fastapi-skeleton: correctly flagged a broken shared venv (its diagnosis held up under lead re-verification) and a repo-wide pytest sys.path gap; finished after both were fixed, 3 passed, clean compile, commit a971d428, merged into phase branch, in-review, awaiting judge
- 2026-07-27 judge: done, all three acceptance criteria verified with cited file:line and re-run test output (18 adapter tests green), every applicable gate passes, no defect found

### T-1.0-03: run() contract stub wired to the FastAPI boundary

Status: done
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
- [x] `run(query: Query, context: RequestContext)` is declared as `AsyncIterator[Event]`, and every item it yields is an instance of the `Event` model from T-1.0-01, never a bare string or dict
- [x] Calling `run()` with a valid stub `Query` yields at least one `guard` event and terminates with exactly one `done` event, both schema-valid against the `Event` envelope
- [x] The FastAPI query endpoint validates every request against the `Query` and `RequestContext` Pydantic models at the boundary; posting a body missing a required `Query` field returns HTTP 422, never a 500 or a silent default
- [x] Posting a `Query.text` value over 2000 characters to the endpoint returns a validation error response and never reaches `run()`
- [x] The stub `run()` makes no direct LLM call and no direct tool call; it is a typed scaffold only, deferring the real Guardrail-Think-Plan-Act-Write loop to build phase 2.0

Breakdown:
- [x] `run()` stub implementation
- [x] Query endpoint wiring in `app.py`
- [x] Tests: valid input, invalid input, missing/null input on the query endpoint; stub-yield shape test on `run()`

Evidence:
- Test suite, judge-run: `source venv/bin/activate && python -m pytest tests/ -q` returned `173 passed, 1 warning in 0.26s`. Core subset `python -m pytest tests/system_03_search_agent/core -q` returned `12 passed in 0.02s`; the endpoint file `test_query_endpoint.py` contributes 15 of the 18 adapter tests.
- Compile: `python -m py_compile` over the four phase modules exited 0.
- AC1: `run.py:17` is `async def run(query: Query, context: RequestContext) -> AsyncIterator[Event]`, with `AsyncIterator` imported from `collections.abc` at `run.py:10`. `test_run.py:36-37` asserts `inspect.isasyncgenfunction(run)`; `test_run.py:39-42` asserts the return annotation names both `AsyncIterator` and `Event`; `test_run.py:47-51` asserts every yielded item is an `Event` instance, which rules out a bare string or dict.
- AC2: `run.py:27-34` yields the `guard` event, `run.py:44-51` yields the `done` event, both constructed through the `Event` model so envelope validation runs on every yield. `test_run.py:54-57` (at least one `guard`), `test_run.py:74-78` (exactly one `done`, and it is last), `test_run.py:60-65` and `test_run.py:81-88` (each payload re-parsed through `GuardPayload` and `DonePayload` respectively). `test_run.py:98-103` additionally asserts `seq` starts at 0, is monotonic, and has no repeats, and `test_run.py:106-109` asserts `ts` is timezone-aware.
- AC3: `app.py:22-26` declares `QueryRequest` with `model_config = ConfigDict(extra="forbid")` wrapping the `Query` and `RequestContext` models, and `app.py:34` types the path function parameter as `request: QueryRequest`, so FastAPI validates the body before the function body runs. `test_query_endpoint.py:66-71` deletes `query.text` and asserts 422; `:87-92` deletes the whole `query` object and asserts 422; `:94-99` deletes `context` and asserts 422; `:128-131` posts `{}` and asserts 422 explicitly rather than 500; `:101-106` and `:108-113` assert 422 on an out-of-enum `surface` and `audience_depth`; `:115-119` and `:121-126` assert 422 on an unknown field at both the top level and inside `query`, proving `extra="forbid"` reaches the wire.
- AC4: `test_query_endpoint.py:73-78` posts a 2001-character `text` and asserts 422, and `:80-85` posts exactly 2000 and asserts 200, pinning the boundary rather than only the failure side. The "never reaches `run()`" half is dispositive from the status code: FastAPI returns 422 only from `RequestValidationError`, which is raised during request-body validation before the path operation function is entered, so a 422 is proof the endpoint body never ran. Had `run()` been reached the response would have been 200.
- AC5: `run.py` imports only `time`, `collections.abc.AsyncIterator`, `datetime`, and the two contracts modules (`run.py:9-14`). No LiteLLM, provider SDK, tools, or harness import exists. `test_run.py:112-123` asserts the module source contains none of `litellm`, `anthropic`, `openai`, `system_03_search_agent.tools`, or `system_03_search_agent.harness`.
- Gate result, type hints: pass. `run.py:17` and `app.py:18, 34` all carry parameter and return annotations; every test helper is annotated too.
- Gate result, snake_case: pass.
- Gate result, endpoint tests for valid, invalid, and missing input: pass. 5 valid-path tests (`test_query_endpoint.py:27-62`) and 10 invalid or missing-input tests (`:65-131`).
- Gate result, explicit-schema constraint on the request direction: pass. `QueryRequest`, `Query`, and `RequestContext` all set `extra="forbid"`, proven over HTTP by `test_query_endpoint.py:115-126`.
- Gate result, secrets: pass. No credential literal added.
- Gate result, v1 scope boundary: pass. The stub emits two events and calls nothing; no compute tool, no BLAST, no sequence-similarity search, no VCF ingestion anywhere in the branch diff.
- Inherited weakness, tracked against T-1.0-01 not this ticket: `app.py:33` declares `response_model=list[Event]`, which is a validation no-op on payload contents because `Event.payload` is an open `dict[str, Any]`. `core/run.py:33, 50` pass `payload=<model>.model_dump()`, so the typed payload is flattened to an unvalidated dict on the way out. The fix belongs in `contracts/events.py`, which is T-1.0-01's file, not a file this ticket may modify. Filed as F-1.0-01.
- Not reproduced: the builder's "ruff clean" claim could not be re-run by the judge. `python -m ruff check src tests` returned `No module named ruff` in the shared venv, so this judge neither confirms nor disputes it. Ruff is declared in `pyproject.toml:31` under the `dev` extra but is not installed. Lint is not one of this ticket's acceptance criteria, so it does not gate the close.

History:
- 2026-07-27 lead: created, scoped from Section 2.1 and Section 1.4-1.5, phase 1.0 open, depends on T-1.0-01 and T-1.0-02
- 2026-07-27 lead: reviewed with product owner, stub scope (guard + done only, not all eleven event types) confirmed as-is, no blocking feedback, refined
- 2026-07-27 builder-run-stub: claimed, built directly on phase branch (sole active builder, no worktree needed)
- 2026-07-27 builder-run-stub: finished, 173 passed (full suite), clean compile, ruff clean, commit cf630a9, in-review, awaiting judge
- 2026-07-27 judge: done, all five acceptance criteria verified with cited file:line and re-run test output, every applicable gate passes; the open-payload weakness it inherits is F-1.0-01 against T-1.0-01, not a defect in this ticket's own files

## Findings

The adversary pass runs at stage 8 of the build cadence. The two findings below were raised earlier, by the judge at stage 7, because they are the basis of the T-1.0-01 rejection.

### F-1.0-01: The event envelope does not bind any of the eleven typed payload models

Status: confirmed
Raised by: judge
Severity: high
Ticket: T-1.0-01

`src/system_03_search_agent/contracts/events.py:195` types the envelope payload as `payload: dict[str, Any]`. All eleven Section 2.3 payload models exist and are individually correct, but nothing connects them to the envelope, so every `max_length` and `max_items` cap on those models is unenforced on any event the system actually emits.

Reproduction, judge-run with `PYTHONPATH=src`:

- `Event(type="guard", version="v1", trace_id="t", seq=0, ts=<now>, payload={"totally": "unknown", "blob": "x"*200000, "nested": {"a": [1,2,3]}})` is accepted. Printed: `PROBE1 open-dict payload accepted, keys= ['totally', 'blob', 'nested'] blob_len= 200000`.
- `Event(type="done", version="v1", trace_id="t", seq=1, ts=<now>, payload={"passed": True, "category": "ok"})` is accepted, so `type` does not in fact discriminate the payload. Printed: `PROBE2 type=done carrying a guard payload accepted: done {'passed': True, 'category': 'ok'}`.

Why this is not a deferrable v1.1 concern: `core/run.py:33` and `run.py:50` already emit `payload=<model>.model_dump()`, and `adapters/web_sse/app.py:33-35` already serializes those envelopes out of the process through `response_model=list[Event]`. Unvalidated envelopes cross a process boundary today, not in a later phase. Section 2.3 states plainly that "`type` discriminates the payload shape", and `production-standards`' multi-agent pipeline gate requires validation at every hop with `maxLength` and `maxItems` binding, precisely to cap blast radius when an upstream payload goes hostile.

What must change: bind the payload to its type, most directly with a Pydantic discriminated union keyed on `type`, so `Event` rejects both an unknown-keyed payload and a payload whose shape does not match its declared `type`. Add a test asserting each mismatch is rejected, including the two probes above as regression cases. Section 2.2's `"payload": {"type": "object"}` describes the wire schema and does not forbid a tighter in-process model; the JSON that model serializes to still satisfies it.

### F-1.0-02: `RequestContext.session_memory` accepts an unbounded arbitrary object at the HTTP boundary

Status: confirmed
Raised by: judge
Severity: medium
Ticket: T-1.0-01

`src/system_03_search_agent/contracts/query.py:29` types `session_memory` as `Any | None`, a documented placeholder for the `SessionMemorySummary` that Section 14 defers to build phase 4.5. `Any` is not an empty placeholder, it is an open door: it accepts any structure of any size through a public endpoint.

Reproduction, judge-run against the live app: `POST /query` with `context.session_memory` set to `{"junk": "z"*500000, "nested": [[["deep"]]]}` returned `HTTP 200`. Printed: `HTTP boundary accepted 500KB arbitrary session_memory -> 200`.

Nothing in phase 1.0 reads this field, so the safe placeholder until phase 4.5 is a type that accepts only `None`, which fails closed and forces an explicit change when the real model lands. If a permissive shape is genuinely wanted now, it needs a bounded one: a typed model with `max_length` on its strings and `max_items` on its arrays, per the bounded-context-items clause of the multi-agent pipeline gate.
