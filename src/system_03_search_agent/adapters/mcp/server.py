"""The outbound-only MCP server: build phase 4.1, `tracker/phase_4.1.md`.

Spec: `requirements/Technical_specification.md` Section 13.2 (the MCP
server, outbound-only), Section 9.1 (`CitationPayload`, referenced not
restated), Decision 24 and the 2026-07-22 Step 2.3-to-Phase-4 decision
(direct Python tools, no inbound MCP; MCP is outbound delivery only).

Exposes exactly one MCP tool, `ask_biomedical_question`, wrapping the SAME
core agent loop `adapters/web_sse/app.py` already drives (via
`RunRegistry.create_run`/`RunRegistry.subscribe`), never the seven internal
tools directly. Request/response, not streaming: this module subscribes to
a run's event stream, waits for the terminal `done` (or a fatal `error`),
and folds everything into one JSON result matching Section 13.2's locked
schema. No `think`, `plan`, or `tool_start` event ever reaches an MCP
caller, and `operator_mode` is hard-pinned `False` here regardless of the
authenticated account's `OPERATOR_USER_IDS` allowlist status, so no MCP
response can ever carry a cost field, a stricter rule than every other
adapter's role-derived filtering (Section 13.2's own "Cost visibility"
paragraph).

Depends on:
    - mcp==2.0.0 (mcp.server.mcpserver.Context, mcp.server.mcpserver.
      MCPServer, mcp.shared.exceptions.MCPError, mcp_types.INVALID_REQUEST):
      read from the installed wheel directly, not from memory or from
      context7 (indexed only to SDK v1.12.4, a different, incompatible
      import path). See tracker/phase_4.1.md's pre-build source read.
    - system_03_search_agent.auth.dependencies (resolve_user_from_bearer_
      token, InvalidBearerTokenError): the exact decode-then-lookup logic
      `get_current_user` uses, extracted so this non-FastAPI caller can
      reuse it without duplicating it.
    - system_03_search_agent.contracts.events (CitationPayload,
      DonePayload, ErrorPayload, GuardPayload, TokenPayload,
      TrustSignalPayload): the Section 2.3 payload models this module
      folds events against. `CitationPayload` is reused verbatim as
      Section 13.2's `CitationV1`, never redefined.
    - system_03_search_agent.contracts.query (Query, RequestContext): the
      one request shape every surface builds before calling into the core.
    - system_03_search_agent.core.run_registry (default_registry): the
      SAME registry instance `adapters/web_sse/app.py` already uses. This
      module never builds a second registry.
    - system_03_search_agent.data.session (session_scope): one DB session
      per tool call, to resolve the caller's bearer token to a `User` row.

Reads:
    - The `Authorization` header on the incoming MCP HTTP request, via
      `Context.headers`.

Writes:
    - Nothing directly. `RunRegistry.create_run` starts the same
      background task every surface starts; this module only reads its
      event stream back.

A design note on "Pydantic input/output models" (tracker/phase_4.1.md's own
phrasing for this ticket): the SDK derives a tool's advertised
`input_schema` from the Python function's own PARAMETERS, one schema
property per parameter (verified against the installed wheel: a single
Pydantic model taken as one parameter becomes one NESTED property named
after that parameter, not a flat top-level schema). Section 13.2's locked
input_schema is flat (`query`, `audience_depth`, `session_id` all at the
top level), so `ask_biomedical_question` below declares three individual,
`Annotated[..., Field(...)]`-constrained parameters rather than a single
`AskBiomedicalQuestionInput` model, which is the SDK-idiomatic way to
express Pydantic field constraints on tool parameters. The OUTPUT side has
no such constraint: a single Pydantic model as the return annotation
becomes the flat output_schema directly, so `AskBiomedicalQuestionOutput`
below is a real Pydantic model, used as documented. Logged as a build
decision in DECISIONS.md.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_REQUEST
from pydantic import BaseModel, ConfigDict, Field

from system_03_search_agent.auth.dependencies import (
    InvalidBearerTokenError,
    resolve_user_from_bearer_token,
)
from system_03_search_agent.contracts.events import (
    CitationPayload,
    DonePayload,
    ErrorPayload,
    GuardPayload,
    TokenPayload,
    TrustSignalPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run_registry import default_registry
from system_03_search_agent.data.models import User
from system_03_search_agent.data.session import session_scope

# Section 13.2's locked output_schema: `citations` maxItems 50, `answer`
# maxLength 8000. Applied twice: once as the Pydantic field constraint
# (so a malformed internal fold would fail loudly rather than ship a
# non-conforming response) and once defensively while folding (see
# `_fold_run_to_response`), the same belt-and-suspenders pattern
# `adapters/web_sse/app.py`'s `_MAX_CITATIONS_PER_RUN` already uses.
_MAX_CITATIONS = 50
_MAX_ANSWER_LENGTH = 8000

_AUTH_FAILURE_MESSAGE = "missing, malformed, or invalid bearer token"


class AskBiomedicalQuestionOutput(BaseModel):
    """Section 13.2's locked `output_schema`, field for field."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(..., max_length=_MAX_ANSWER_LENGTH)
    citations: list[CitationPayload] = Field(..., max_length=_MAX_CITATIONS)
    trust_signal: TrustSignalPayload
    run_id: str = Field(..., max_length=64)


server = MCPServer(
    name="system3-biomedical-search",
    version="1.0.0",
    instructions=(
        "Ask a biomedical research question. Returns a cited answer "
        "assembled from the NCBI knowledge graph and live NCBI APIs, or "
        "an honest refusal."
    ),
)


def _extract_bearer_header(ctx: Context) -> str | None:
    """Read the raw `Authorization` header off the incoming MCP request.

    `Context.headers` is documented by the SDK itself as "client-supplied
    input, never treat one as an identity assertion" (mcpserver/context.py);
    this function only extracts the raw string, `resolve_user_from_bearer_
    token` is what actually verifies it.
    """
    headers = ctx.headers
    if headers is None:
        return None
    return headers.get("authorization")


async def _authenticate_mcp_caller(ctx: Context) -> User:
    """Resolve the calling `User` from the request's bearer token, or raise
    `MCPError` before any run is ever created.

    T-4.1-03 (tracker/phase_4.1.md): a caller with a missing, malformed, or
    invalid bearer token never reaches the core loop at all. This function
    is called before `RunRegistry.create_run`, so no run and no model or
    tool budget is spent on a request that fails here. Reuses
    `auth/dependencies.py`'s `resolve_user_from_bearer_token`, the exact
    decode-then-lookup logic `get_current_user` uses on the REST surface,
    rather than a second, parallel implementation.
    """
    authorization = _extract_bearer_header(ctx)
    with session_scope() as session:
        try:
            return resolve_user_from_bearer_token(authorization, session)
        except InvalidBearerTokenError:
            raise MCPError(code=INVALID_REQUEST, message=_AUTH_FAILURE_MESSAGE) from None


def _fallback_answer_text(
    *, guard_payload: GuardPayload | None, error_payload: ErrorPayload | None
) -> str:
    """Built only when a run's terminal state produced no `token` events at
    all.

    `write_node`'s own cite-or-refuse refusal path (`core/graph.py`)
    always emits a `token` event carrying `build_refusal_text(...)`, so
    that path never reaches here. This function exists for the shapes of
    run ending that never run `write_node` at all: a guardrail-level
    refusal (`_decline_for_guardrail`, which emits `guard` and `done` but
    no `token`) or a daily-cap decline or step-level error before Write
    ever ran (`_decline_for_daily_cap`, which emits a fatal `error` and
    `done`, no `token`). Cite-or-refuse still holds either way: this is
    defensive completeness for the MCP surface's `answer` field, which
    Section 13.2 requires non-empty and present on every response, never a
    second refusal wording competing with `write_node`'s own.
    """
    if guard_payload is not None and not guard_payload.passed:
        reason_suffix = f" ({guard_payload.reason})" if guard_payload.reason else ""
        return (
            "This question could not be answered: it did not pass this "
            f"system's content guardrail{reason_suffix}."
        )
    if error_payload is not None:
        return f"This query could not be completed: {error_payload.message}"
    return "This query could not be completed: the run ended before producing an answer."


async def _fold_run_to_response(run_id: str) -> AskBiomedicalQuestionOutput:
    """Drive `run_id` to its terminal event and fold the result into
    Section 13.2's locked response shape.

    Per Section 13.2: "the adapter waits on the internal event stream
    until done, folding think, plan, and tool_start out entirely and
    folding token and tool_result into the final structured response."
    Concretely: `think`/`plan`/`tool_start`/`tool_result`/`guard`/`cost`
    events are read and discarded (none of them map onto any field this
    response carries); `token` events are concatenated into `answer`
    (`_narrative_chunks` in `core/graph.py` already terminates every
    chunk it emits with a trailing space, so plain concatenation
    reconstructs the narrative with no extra join logic needed);
    `citation` events become `citations`; the answer-scope `trust_signal`
    event (there is at most one; `citation`-scoped ones are per-claim and
    are not surfaced here, since Section 13.2's output carries one
    `trust_signal` object, not a list) becomes `trust_signal`.

    Some terminal shapes emit no answer-scope `trust_signal` event at all
    (the no-tool-selected path in `write_node`, and every early-exit path
    that never reaches `write_node`), so a synthetic one is built from the
    terminal `done` event's `trust_outcome` when none was observed. This
    guarantees Section 13.2's "all four output fields required" even on a
    run shape that never itself emits a per-run `trust_signal` event.
    """
    answer_parts: list[str] = []
    citations: list[CitationPayload] = []
    answer_trust_signal: TrustSignalPayload | None = None
    terminal_trust_outcome: Literal["answer", "flag", "ask", "refuse"] | None = None
    guard_payload: GuardPayload | None = None
    fatal_error_payload: ErrorPayload | None = None

    async for event in default_registry.subscribe(run_id, after_seq=-1):
        if event.type == "token":
            answer_parts.append(TokenPayload(**event.payload).text)
        elif event.type == "citation":
            if len(citations) < _MAX_CITATIONS:
                citations.append(CitationPayload(**event.payload))
        elif event.type == "trust_signal":
            candidate = TrustSignalPayload(**event.payload)
            if candidate.scope == "answer":
                answer_trust_signal = candidate
        elif event.type == "guard":
            guard_payload = GuardPayload(**event.payload)
        elif event.type == "error":
            payload = ErrorPayload(**event.payload)
            if payload.fatal:
                fatal_error_payload = payload
        elif event.type == "done":
            terminal_trust_outcome = DonePayload(**event.payload).trust_outcome
        # "think", "plan", "tool_start", "tool_result", and "cost" carry
        # nothing this response's schema has a field for; discarded by
        # simply not matching any branch above.

    if answer_trust_signal is None:
        resolved_outcome = terminal_trust_outcome or "refuse"
        answer_trust_signal = TrustSignalPayload(
            outcome=resolved_outcome,
            risk_tier="low",
            grounded=resolved_outcome == "answer",
            triangulated=None,
            citation_id=None,
            scope="answer",
        )

    answer_text = "".join(answer_parts).strip()
    if not answer_text:
        answer_text = _fallback_answer_text(
            guard_payload=guard_payload, error_payload=fatal_error_payload
        )
    answer_text = answer_text[:_MAX_ANSWER_LENGTH]

    return AskBiomedicalQuestionOutput(
        answer=answer_text,
        citations=citations,
        trust_signal=answer_trust_signal,
        run_id=run_id,
    )


@server.tool(
    description=(
        "Ask a biomedical research question. Returns a cited answer "
        "assembled from the NCBI knowledge graph and live NCBI APIs, or "
        "an honest refusal."
    )
)
async def ask_biomedical_question(
    query: Annotated[str, Field(max_length=2000)],
    ctx: Context,
    audience_depth: Literal["clinical_brief", "researcher", "deep_technical"] = "researcher",
    session_id: Annotated[str | None, Field(max_length=64)] = None,
) -> AskBiomedicalQuestionOutput:
    """The one MCP tool this server advertises (Section 13.2).

    Auth-first: `_authenticate_mcp_caller` runs before anything else in
    this function body, so a caller with a missing, malformed, or invalid
    bearer token never reaches `RunRegistry.create_run` (T-4.1-03).

    `session_id` is optional on this surface (Section 13.2's own locked
    input_schema requires only `query`), unlike `Query.session_id`, which
    is a required field on the shared contract every surface builds. When
    omitted, this handler defaults it to the freshly minted `run_id`: an
    MCP tool call is request/response, not a live session (Section 13.2's
    own framing), and session-memory reuse across separate MCP calls is
    not built until build phase 4.5, so a synthetic per-call session_id is
    the correct placeholder rather than inventing session continuity this
    phase does not implement. Logged as a build decision in DECISIONS.md.
    """
    user = await _authenticate_mcp_caller(ctx)

    run_id = str(uuid.uuid4())
    query_obj = Query(
        text=query,
        session_id=session_id if session_id is not None else run_id,
        trace_id=run_id,
        user_id=str(user.id),
        audience_depth=audience_depth,
    )
    # T-4.1-03: `operator_mode` is hard-set `False` here in code, never
    # derived from `is_operator_user`. This is the single strongest lever
    # against a cost field ever reaching an MCP response: even an
    # allowlisted operator account calling through this surface gets
    # `operator_mode=False`, and `_fold_run_to_response` above never reads
    # a cost-shaped field out of any event regardless.
    context = RequestContext(surface="mcp", operator_mode=False)
    default_registry.create_run(query_obj, context, run_id=run_id)
    return await _fold_run_to_response(run_id)
