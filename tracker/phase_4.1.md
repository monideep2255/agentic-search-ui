# Phase 4.1: outbound-only MCP server wrapping the same tool functions

Build phase 4.1 exposes System 3 outward to persona 11 (AI agents and MCP or LLM consumers) via a System 3-authored MCP server, wrapping the same core `run()` loop build phase 4.0 finalized behind `adapters/web_sse/`, never the seven internal tools directly and never a new parallel auth system.

Depends on: build phase 3.4 (done, PR #28, merged). Also draws on build phase 4.0 (done, PR #39, merged), since it wraps the same `RunRegistry`/`run_streaming` core that phase finalized, though Section 25 names only 3.4 as the hard dependency.
Branch: `phase/4.1-mcp-server`
Spec: `requirements/Technical_specification.md` Section 13.2 (the MCP server, outbound-only), Section 9.1 (`CitationPayload`, referenced not restated), Section 13.5 (per-surface summary table), Decision 24 and the 2026-07-22 Step 2.3-to-Phase-4 decision (direct Python tools, no inbound MCP; MCP is outbound delivery only)
Reference: `docs/build/Build_workflow_cadence.md`, `LEARNINGS.md` (zero entries in this phase's territory as of open: searched "mcp server", "api key", "outbound", "scoped credential", zero hits)

## New dependency, approved before this phase opened

The official `mcp` Python SDK (PyPI: `mcp`, latest `2.0.0`, MIT license, maintained by the Model Context Protocol project under LF Projects LLC, repo `github.com/modelcontextprotocol/python-sdk`). Supply-chain check run 2026-08-11 before any code: no compromise reports, no postinstall/setup.py execution risk (wheel-only), long actively-maintained version history (0.9.1 through 2.0.0), maintainer emails resolve to the project's own Anthropic-affiliated engineers. Product owner approved adding it floor-pinned (`mcp>=2.0`) matching this repo's existing convention for the rest of the stack, per `.claude/rules/ai-security-standards.md`'s "ask before adding a new dependency" gate, which stays active in bossman mode.

## Phase premise (the done-when)

An MCP client holding a valid bearer token for its own dedicated User account calls the single advertised tool, `ask_biomedical_question`, with a real biomedical question. It receives one JSON result, never a stream: no `think`, `plan`, or `tool_start` event ever reaches it, and the internal `token`/`tool_result`/`citation`/`trust_signal` events are folded into a final `answer`, `citations`, `trust_signal`, `run_id` shape matching Section 13.2's locked schema exactly, `CitationV1` read verbatim off `contracts/events.py`'s existing `CitationPayload` (Section 9.1's provenance type, not a redefinition). A query with no groundable answer gets the honest refusal string in `answer` with no fabricated citations, the identical cite-or-refuse behavior every other surface already gets, not a weaker or different rule for this one. No response the MCP surface ever returns, for any caller, in any role, carries a cost field: `operator_mode` is hard-pinned false for this surface regardless of `is_operator_user`, which is a different, stronger rule than every other adapter's role-derived filtering. A caller with a missing, malformed, or invalid bearer token never reaches the core loop at all: no run is created, no model or tool budget is spent, and the caller gets a protocol-level auth failure, not a silent empty or malformed result. `list_tools()` advertises exactly one tool; no internal tool (`cypher_query`, `ncbi_efetch`, `ncbi_dbsnp`, `pubtator_annotate`, `litvar2_lookup`, `pathogen_detection`, `clinicaltrials_search`) is ever reachable as a separate MCP tool, closing the raw-passthrough risk Section 13.2 names explicitly.

The verify surface is `tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py`, not a suite total, per `tracker/phase_3.1.md`'s standing rule.

## Scope boundary, decided rather than asked (v1-scope-boundary check)

Section 13.2 states an MCP client "gets its own cost-cap and rate-limit bucket tracked the same way as any REST API key." This repo has no first-class "API key" entity anywhere today (confirmed by pre-build read below): every surface authenticates via a bearer JWT that decodes to a `User` row, and every cost cap (`check_per_query_cap`, `check_user_daily_query_cap`, `check_system_daily_cost_cap`) already keys off `trace_id` or `user_id`, never a key-shaped identity. Building a new API-key-as-entity system to satisfy this line literally would be new architecture invented mid-phase, exactly what `.claude/rules/v1-scope-boundary.md` exists to stop, and it is not named as a fast-follow trigger anywhere. Read plainly instead: an MCP client's "own scoped API key" is a dedicated `User` account provisioned for that client, authenticating with the same bearer-JWT mechanism every other surface already uses. The existing per-user daily cap and per-query cap then apply automatically, with zero new mechanism, because they already key off `user_id`. This is the same "wraps the one core's contract, not around it" reading Section 13.2 itself states for the tool surface, applied here to auth. Flagged rather than silently substituted, per the rule's own instructions.

## Pre-build source read (done before any code, before any ticket)

Per `.claude/rules/attack-the-constraint.md` and this repo's standing pre-build-probe pattern (phases 3.2/3.3/3.5/4.0), every file this phase touches or wraps was read before scoping tickets, and the actual installed `mcp==2.0.0` SDK source was read directly rather than trusted from memory or from `context7`'s docs (which only index up to SDK `v1.12.4`, a version behind and, per the module rename found below, API-incompatible in import path).

| Read | Finding |
|------|---------|
| `adapters/web_sse/app.py` | `POST /v1/query` (line 170) calls `default_registry.create_run(query, context, run_id=run_id)`; `RequestContext` is built at line 169 with `surface="rest_sse"`; the authenticated user comes from `Depends(get_current_user)` (line 159); `is_operator_user(str(current_user.id))` is called at line 277 |
| `core/run_registry.py` | `async def subscribe(self, run_id, *, after_seq=-1) -> AsyncIterator[Event]` (line 462) yields every `Event` with `seq > after_seq` and stops on `event.type == "done"` or a fatal `error` (lines 512-515). This is the exact interface to await-until-done with no SSE framing: iterate it and stop at the terminal event |
| `core/run.py` | `async def run_streaming(query, context) -> AsyncIterator[Event]` (line 191) is the underlying generator `create_run`'s background task drives; not called directly by this phase, `RunRegistry` already owns the lifecycle |
| `contracts/query.py` | `RequestContext` (lines 65-86) carries exactly `surface: Literal["web_ui", "rest_sse", "mcp", "cli"]`, `session_memory`, `operator_mode: bool = False`. `"mcp"` is already a legal literal value, added in an earlier phase, unused until now. `query`, `audience_depth`, `session_id` live on `Query` (lines 21-63), not `RequestContext` |
| `contracts/events.py` | `CitationPayload` (lines 135-151) already carries every field Section 13.2's `CitationV1` names: `source`, `source_id`, `source_url` (host-pinned pattern), `layer`, `evidence_kind`, `assertion_confidence`, `population_ancestry_context`, `license`, plus `citation_id`, `display_index`, `field`, `claim_text`. Reused verbatim, never redefined. `DonePayload` (lines 224-230) carries `total_cost_usd`, the exact field this phase must never let reach an MCP response |
| `auth/dependencies.py` | `get_current_user(authorization: str \| None = Header(...), session=Depends(get_session)) -> User` (line 34) parses `"Bearer <token>"` (lines 46-50), decodes via `decode_access_token(token)` (line 52), looks up the `User` row (line 61). No API-key entity exists; confirms the scope-boundary reading above. `get_current_user` is a FastAPI-DI function, not directly callable from an MCP `Context`; its inner decode-then-lookup logic is what this phase's auth ticket reuses, not the DI wrapper itself |
| `harness/cost_control.py` | `is_operator_user(user_id)` (line 502) checks the `OPERATOR_USER_IDS` env allowlist. `check_per_query_cap` keys on `trace_id`; `check_user_daily_query_cap` and `check_system_daily_cost_cap` key on `user_id` via the `interactions` table. None key on an API key, confirming no per-key bucket exists to plug into even if this phase wanted one |
| `mcp==2.0.0` SDK, read from the actual downloaded wheel, not `context7` (indexed only to `v1.12.4`, a different import path) | `MCPServer` (`mcp/server/mcpserver/server.py:147`), not `FastMCP`, the pre-2.0 name. `@server.tool(...)` (`server.py:621`) and `add_tool` derive both input and output JSON Schema from the tool function's Python type hints and Pydantic return annotation via `func_metadata()`; there is no `input_schema=`/`output_schema=` literal-dict parameter. `MCPServer.streamable_http_app(stateless_http=True, ...)` (`server.py:1218`) returns a plain `starlette.applications.Starlette` app, mountable in FastAPI via `app.mount("/mcp", ...)`. A `Context` parameter injected into a tool function (detected by type annotation, `mcpserver/utilities/context_injection.py:13-46`) exposes `ctx.headers` (`mcpserver/context.py:277-285`), a read-only view of the incoming HTTP request's headers, explicitly documented as "client-supplied input, never treat one as an identity assertion". The SDK's own `auth=`/`token_verifier=`/`auth_server_provider=` OAuth machinery is entirely optional and untouched if `auth=None` is never passed to `MCPServer.__init__` (`server.py:236-242`); this phase leaves it unset and does its own auth inside the tool handler by reading `ctx.headers.get("authorization")`. `mcp.shared.exceptions.MCPError` re-raised from a tool body becomes a top-level JSON-RPC protocol error (`tools/base.py:173-179`), the right vehicle for a hard auth failure; any other exception is caught and returned as a normal `CallToolResult(is_error=True, ...)`, never a crashed transport (`server.py:423-424`) |
| `tests/system_03_search_agent/adapters/web_sse/test_phase_4_0_premise.py` | Established in-process test pattern: `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` against the real FastAPI app, no mocked transport. This phase's premise gate reuses the same pattern against the mounted MCP Starlette sub-app, driven by the real `mcp` client SDK (`mcp.client.streamable_http`), not a hand-rolled JSON-RPC payload |

## Ticket map

| Ticket | Slice | Files | Status |
|--------|-------|-------|--------|
| T-4.1-01 | The premise gate, blocking | `tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py` (new) | in-review |
| T-4.1-02 | `adapters/mcp/server.py`: `MCPServer` instantiation, `ask_biomedical_question` registered via `@server.tool(...)` against Pydantic input/output models that literally encode Section 13.2's locked schema (`Field(..., max_length=2000)` on `query`, the three-value `audience_depth` enum, `max_length=64` on `session_id` and `run_id`, `max_length=8000` on `answer`, `max_length=50` on `citations` using `contracts.events.CitationPayload` verbatim, `trust_signal` as a plain object, all four output fields required); the fold loop that iterates `RunRegistry.subscribe(run_id, after_seq=-1)` to the terminal event, discarding `think`/`plan`/`tool_start`, and assembling the final response from `token`/`tool_result`/`citation`/`trust_signal`/`done`; `streamable_http_app(stateless_http=True)` mounted into the existing FastAPI app at `/mcp` | `src/system_03_search_agent/adapters/mcp/server.py` (new), `src/system_03_search_agent/adapters/mcp/__init__.py` (new), `src/system_03_search_agent/adapters/web_sse/app.py` (mount only) | in-review |
| T-4.1-03 | Auth: a `Context`-parameter tool handler reads `ctx.headers.get("authorization")`, strips the `Bearer ` prefix, and resolves a `User` via the SAME decode-then-lookup logic `auth/dependencies.py`'s `get_current_user` already uses (extracted into a small callable both the FastAPI dependency and this handler call, not duplicated). Missing, malformed, or invalid token raises `MCPError` before `create_run` is ever called, so no run and no budget is spent. `RequestContext(surface="mcp", operator_mode=False)` is constructed with `operator_mode` hard-set `False` in code, never derived from `is_operator_user`, so no MCP response can ever carry a cost field regardless of the authenticated account's allowlist status | `src/system_03_search_agent/adapters/mcp/server.py`, `src/system_03_search_agent/auth/dependencies.py` (extract the decode-then-lookup helper, no behavior change to the existing FastAPI dependency) | in-review |
| T-4.1-04 | Dependency and wiring: add `mcp>=2.0` to `requirements.txt` and `pyproject.toml`; log the dependency-addition and the API-key-as-User-account scope-boundary reading to `DECISIONS.md`; confirm `list_tools()` advertises exactly one tool with no internal tool ever separately reachable | `requirements.txt`, `pyproject.toml`, `DECISIONS.md` | in-review |

Depends-on chain: T-4.1-01 blocks everything (written and watched failing first, committed on its own before any implementation, per the corrected process F-4.0-J-02 named for future phases). T-4.1-02 is the foundation; T-4.1-03 depends on it (the tool handler it adds auth to). T-4.1-04 depends on nothing but T-4.1-01, can land alongside T-4.1-02.

Dispatch plan: single-builder sub-agent, not an agent team. tmux is not available this session (checked, `tmux: ok` but not running inside one), and the work does not decompose into independent, non-overlapping pieces regardless: the fold loop, the schema models, and the auth handler all live in the same new small module and are tightly coupled by construction. Splitting this across parallel builders would create exactly the kind of overlapping-write collision `plan-then-fan-out.md` and the worktree-isolation policy exist to prevent, for no speed benefit, since there is nothing to parallelize.

## Premise gate design

Written and watched failing before `adapters/mcp/server.py` exists, per LEARNINGS.md row 43's discipline (every failure `ModuleNotFoundError`, never a network fault or a fixture bug), and per F-4.0-J-02's corrected process: the gate lands in its own commit, its failing run's real output gets pasted into this file, and only then does implementation start.

### The arms (planned)

| Arm | Cases | What it pins |
|-----|-------|---------------|
| Golden path | A real biomedical question (reusing one of the seven v1 must-pass moat questions) through a real `mcp` client session against the mounted Starlette app; assert non-empty `answer`, at least one well-formed `citations` entry matching `CitationPayload`'s shape, a present `trust_signal`, a present `run_id` | The request/response fold actually produces a grounded answer end to end |
| Refusal path | A query engineered to return zero groundable results; assert the honest refusal string in `answer`, no fabricated citations, same cite-or-refuse rule every other surface already enforces (production-standards' AI answer grounding gate), not a weaker MCP-specific rule | This surface never becomes a second, laxer path to a confident wrong answer |
| Event folding | Assert the folded response schema structurally has no field for `think`/`plan`/`tool_start`/`token`/`tool_result`, and that a run which does emit them completes without the fold loop hanging or crashing | Section 13.2's fold rule is a structural guarantee, not a hope |
| Never-cost | A caller authenticated as a `User` on the `OPERATOR_USER_IDS` allowlist still gets a response with no cost-shaped field anywhere, proving `operator_mode` is hard-pinned false for this surface and not merely defaulted false | The stronger, surface-level rule Section 13.2 states, distinct from every other adapter's role-derived filtering |
| Auth, missing token | No `Authorization` header: `MCPError`, no run created (assert via a spy/count on `RunRegistry.create_run` or an equivalent observable), no budget spent | The auth boundary fails closed before any cost is incurred |
| Auth, invalid token | A malformed or expired bearer token: same as above | Closes the "garbage token silently becomes an anonymous run" gap |
| Auth, valid token | A real test `User`'s valid bearer token succeeds and the resulting run's owner matches that user | Confirms the reused decode-then-lookup path actually works, not just that it rejects |
| Tool surface | `list_tools()` returns exactly one tool named `ask_biomedical_question`; none of the seven internal tool names are ever separately advertised or callable | Closes the raw-passthrough risk Section 13.2 names by name |
| Schema fidelity | The tool's advertised `input_schema`/`output_schema` (as `list_tools()` reports them, derived by the SDK from the Pydantic models) match Section 13.2's locked field list and constraints: `query` maxLength 2000 required, `audience_depth` three-value enum, `session_id` maxLength 64, `answer` maxLength 8000, `citations` maxItems 50, `trust_signal` object, `run_id` maxLength 64, all four output fields required | The locked spec schema is what ships, not an approximation the SDK happened to infer |

Not covered by this gate, stated per `.claude/rules/goal-contracts.md`'s coverage-declaration discipline: real interop against an external MCP host (Claude Desktop or another live MCP client), since that needs a live external tool this environment cannot drive; true multi-process behavior and load-scale concurrency across many simultaneous MCP clients, which is build phase 6.0's named rate-limiting and concurrency territory, the same carve-out build phase 4.0 already used for its own load-scale exclusion; and the OAuth 2.0/OIDC alignment the Step 6.2 new-intake note flags as a future direction, since this phase deliberately keeps the SDK's own OAuth provider machinery unwired in favor of reusing the existing bearer-JWT mechanism (see the scope-boundary note above).

## Premise gate, failing-first

`tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py` landed alone, before `adapters/mcp/server.py` existed, commit `3014dae` ("test(mcp-server): add the phase 4.1 premise gate, watched failing first"). Every arm from the design table above is present: `TestToolSurface` (2 cases plus a callability check), `TestSchemaFidelity` (2 cases), `TestGoldenPath`, `TestRefusalPath`, `TestEventFolding`, `TestNeverCost`, `TestAuth` (4 cases: missing, malformed, invalid, valid token).

An early draft imported the not-yet-existing module only inside `TestToolSurface`/`TestSchemaFidelity`, while the HTTP-driven classes (`TestGoldenPath` and the rest) imported the already-existing `adapters/web_sse/app.py` at module level and only failed once they actually tried to reach `/mcp`. Against the pre-implementation baseline that surfaced as `mcp.shared.exceptions.MCPError: Not Found` (an HTTP 404 through the not-yet-mounted app), a real and accurate signal that the endpoint does not exist, but not the uniform `ModuleNotFoundError` LEARNINGS.md row 43 requires, and shaped exactly like the "network fault" the discipline exists to rule out. Fixed with an autouse fixture (`_require_mcp_server_module`) that explicitly imports `system_03_search_agent.adapters.mcp.server` before every test in the file, so every case fails the same way regardless of which path it exercises.

Real run, against the corrected test file, before any implementation existed:

```text
$ pytest tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py -v
============================= test session starts ==============================
platform darwin -- Python 3.11.6, pytest-9.1.1, pluggy-1.6.0
plugins: cov-7.1.0, asyncio-1.4.0, anyio-4.14.2, langsmith-0.10.10
collected 13 items

TestToolSurface::test_exactly_one_tool_is_advertised ERROR                 [  7%]
TestToolSurface::test_no_internal_tool_name_is_separately_advertised ERROR [ 15%]
TestToolSurface::test_no_internal_tool_is_separately_callable ERROR        [ 23%]
TestSchemaFidelity::test_input_schema_matches_section_13_2 ERROR           [ 30%]
TestSchemaFidelity::test_output_schema_matches_section_13_2 ERROR          [ 38%]
TestGoldenPath::test_a_real_question_returns_a_grounded_cited_answer ERROR [ 46%]
TestRefusalPath::test_a_zero_groundable_result_query_refuses_honestly ERROR[ 53%]
TestEventFolding::test_folded_response_has_no_field_for_excluded_event_types ERROR [ 61%]
TestNeverCost::test_an_operator_allowlisted_caller_still_gets_no_cost_field ERROR  [ 69%]
TestAuth::test_missing_token_is_rejected_before_any_run_is_created ERROR   [ 76%]
TestAuth::test_malformed_token_is_rejected_before_any_run_is_created ERROR [ 84%]
TestAuth::test_invalid_token_is_rejected_before_any_run_is_created ERROR   [ 92%]
TestAuth::test_a_valid_token_succeeds_and_the_run_is_owned_by_that_user ERROR [100%]

==================================== ERRORS ====================================
____ ERROR at setup of TestToolSurface.test_exactly_one_tool_is_advertised _____
    @pytest.fixture(autouse=True)
    def _require_mcp_server_module() -> None:
        ...
>       import system_03_search_agent.adapters.mcp.server  # noqa: F401
E       ModuleNotFoundError: No module named 'system_03_search_agent.adapters.mcp.server'

tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py:383: ModuleNotFoundError

[... the same ModuleNotFoundError, from the same fixture, repeats for all 13 cases ...]

=========================== short test summary info ============================
ERROR (x13), same ModuleNotFoundError each time
============================== 13 errors in 4.43s ==============================
```

13 of 13 cases failed, every failure `ModuleNotFoundError: No module named 'system_03_search_agent.adapters.mcp.server'` raised from the same autouse fixture, zero passes, zero network faults, zero fixture bugs. The `search_agent_users` PostgreSQL database was reachable this run, so the HTTP-driven classes were not skipped; they failed via the same import guard before ever attempting a request. Implementation started only after this run.

### Final passing run, after implementation (commits `631ab7a`, `699cd4c`, `6665428`, `d666066`, `dccb4d0`)

Getting from 13/13 failing to 13/13 passing needed two intermediate fix rounds against the real implementation, each a genuine defect in the mount recipe or the test harness, not a premise-gate mistake: the mount needed `streamable_http_path="/"` plus an explicit `lifespan=` wiring (6 of 13 cases failed with `RuntimeError: Task group is not initialized` before this), and the test harness needed a fresh mounted app per call plus `except* MCPError` to unwrap `anyio`'s `BaseExceptionGroup` wrapping (7 of 13 cases failed for these two reasons after the mount fix). Full account of all five findings: `LEARNINGS.md`'s two 2026-08-11 entries under "Mounting the mcp==2.0.0 SDK's streamable_http_app into FastAPI silently fails three separate ways" and "Testing the mounted MCP endpoint needed two more non-obvious accommodations".

```text
$ pytest tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py -v
============================= test session starts ==============================
collected 13 items

TestToolSurface::test_exactly_one_tool_is_advertised PASSED                [  7%]
TestToolSurface::test_no_internal_tool_name_is_separately_advertised PASSED[ 15%]
TestToolSurface::test_no_internal_tool_is_separately_callable PASSED       [ 23%]
TestSchemaFidelity::test_input_schema_matches_section_13_2 PASSED          [ 30%]
TestSchemaFidelity::test_output_schema_matches_section_13_2 PASSED         [ 38%]
TestGoldenPath::test_a_real_question_returns_a_grounded_cited_answer PASSED[ 46%]
TestRefusalPath::test_a_zero_groundable_result_query_refuses_honestly PASSED [ 53%]
TestEventFolding::test_folded_response_has_no_field_for_excluded_event_types PASSED [ 61%]
TestNeverCost::test_an_operator_allowlisted_caller_still_gets_no_cost_field PASSED  [ 69%]
TestAuth::test_missing_token_is_rejected_before_any_run_is_created PASSED  [ 76%]
TestAuth::test_malformed_token_is_rejected_before_any_run_is_created PASSED[ 84%]
TestAuth::test_invalid_token_is_rejected_before_any_run_is_created PASSED  [ 92%]
TestAuth::test_a_valid_token_succeeds_and_the_run_is_owned_by_that_user PASSED [100%]

============================== 13 passed in 8.78s ==============================
```

Full repo suite (`pytest -q` from repo root): `6 failed, 2410 passed, 113 skipped, 1 xfailed in 66.00s`. The 6 failures are the exact same pre-existing, live-network-opt-in-gated set named in `requirements/phase_6/Continuation_prompt.md` (`test_citation_trust_full_premise.py`, every one a `LiveHttpCallInUnitSuiteError`), confirmed not a regression: develop's baseline is 2397 passing plus 113 skipped plus 1 xfailed plus 6 failed (2517 total); this run adds exactly the 13 new premise-gate tests (2410 = 2397 + 13) with the skip/xfail/fail counts unchanged. `ruff check` is clean on every file this phase touched or created.

## Findings

(Populated by the judge and adversary rounds once dispatched.)
