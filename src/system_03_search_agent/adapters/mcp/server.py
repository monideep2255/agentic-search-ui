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
      MCPServer, mcp.shared.exceptions.MCPError, mcp_types.INVALID_REQUEST,
      mcp_types.INVALID_PARAMS, mcp_types.REQUEST_TIMEOUT): read from the
      installed wheel directly, not from memory or from context7 (indexed
      only to SDK v1.12.4, a different, incompatible import path). See
      tracker/phase_4.1.md's pre-build source read.
    - system_03_search_agent.auth.dependencies (resolve_user_from_bearer_
      token, has_bearer_scheme, InvalidBearerTokenError): the exact
      decode-then-lookup logic `get_current_user` uses, extracted so this
      non-FastAPI caller can reuse it without duplicating it.
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
    - system_03_search_agent.synthesis.trust (aggregate): Section 8.3.4's
      most-restrictive-claim-wins rule, reused verbatim (F-4.1-A-01,
      F-4.1-A-02, fix round 2) rather than a second implementation of the
      same floor logic `core/graph.py`'s write_node already uses.

Reads:
    - The `Authorization` header on the incoming MCP HTTP request, via
      `Context.headers`.
    - The raw JSON-RPC `tools/call` request params, via
      `Context.request_context.params`, to detect a caller-supplied
      argument this tool does not declare (F-4.1-A-13, fix round 2): the
      SDK's own auto-derived argument model silently drops an unknown key
      rather than rejecting it, so this is the one place in the request
      lifecycle this surface can still see what the caller actually sent.

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

import asyncio
import re
import uuid
from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_PARAMS, INVALID_REQUEST, REQUEST_TIMEOUT
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from system_03_search_agent.auth.dependencies import (
    InvalidBearerTokenError,
    has_bearer_scheme,
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
from system_03_search_agent.core.run_registry import (
    ConcurrentRunCapExceededError,
    default_registry,
)
from system_03_search_agent.data.models import User
from system_03_search_agent.data.session import session_scope
from system_03_search_agent.synthesis.trust import aggregate

# Section 13.2's locked output_schema: `citations` maxItems 50, `answer`
# maxLength 8000. Applied twice: once as the Pydantic field constraint
# (so a malformed internal fold would fail loudly rather than ship a
# non-conforming response) and once defensively while folding (see
# `_fold_run_to_response`), the same belt-and-suspenders pattern
# `adapters/web_sse/app.py`'s `_MAX_CITATIONS_PER_RUN` already uses.
_MAX_CITATIONS = 50
_MAX_ANSWER_LENGTH = 8000

_AUTH_FAILURE_MESSAGE = "missing, malformed, or invalid bearer token"

# F-4.10-J-04 / F-4.10-A-08 (judge and adversary round 1, build phase
# 4.10). `RunRegistry.create_run` gained a per-principal concurrent-run
# cap that phase, and this module was not touched, so its one `create_run`
# call site could raise a bare `RuntimeError` out of a tool handler that
# converts every other failure into a typed `MCPError` (Section 13.2's
# whole point: every failure has a declared shape).
#
# The message is a fixed literal, deliberately. `ConcurrentRunCapExceeded
# Error`'s own string embeds the internal namespaced owner id
# (`user:<uuid>`), and `tracker/BOARD.md` records F-4.1-J3-01 against this
# exact habit: raw exception stringification into an external-facing
# message. The caller already knows who they are and gains nothing from
# the internal namespacing, so nothing derived from the exception is
# interpolated here.
#
# It still satisfies production-standards' retry-safety gate, which asks
# that an error say what to do next rather than only what failed: the
# condition is genuinely transient (finishing or stopping a run frees a
# slot immediately), and the sentence says so.
_RUN_CAP_MESSAGE = (
    "you already have the maximum number of runs in flight on this account; "
    "wait a few seconds for one to finish, or stop one on the REST/SSE "
    "surface, then retry this call"
)

# T-4.3-05, build phase 4.3: mirrors `adapters/web_sse/app.py`'s own
# `_CONCURRENT_RUN_CAP_MESSAGES_BY_BOUND` table. `ConcurrentRunCapExceededError`
# now carries a structural `bound` attribute rather than only a message
# string; this surface's catch site below branches on it the same way, so
# a message is looked up by WHICH bound was hit instead of assuming this
# exception type can only ever mean one thing. Only one bound exists today
# (the concurrency cap this registry enforces; a guest's allowance never
# reaches this exception), so this table has one entry, and `.get(...)`
# falls back to the same message for any `bound` this table does not yet
# name.
_RUN_CAP_MESSAGES_BY_BOUND: dict[str, str] = {
    "concurrency": _RUN_CAP_MESSAGE,
}

# F-4.1-A-06 (adversary round 1, fix round 2): a wall-clock bound on the
# fold loop itself, on top of, never instead of, every per-step timeout
# the harness already enforces (`harness/harness.py`'s `_TIER_STEP_
# BUDGET_S`/`_QUERY_CLASS_BUDGET_S`, `.claude/rules/tool-call-budgets.md`).
# Those per-step timeouts live INSIDE the run this surface awaits; a
# defect that lets one of them fail to fire (or a future step that
# forgets to wrap itself) would otherwise hang this surface's single
# request/response call forever, with no way for a caller to know, and
# leak a permanent `RunRegistry` entry immune to both eviction
# (`finished` never becomes `True`) and abandonment cancellation
# (`subscriber_count` stays 1 for as long as this coroutine keeps
# awaiting). The value is derived from the harness's own published
# worst case for one full Guardrail->Think->Plan->Act->Write loop, not
# invented: `_TIER_STEP_BUDGET_S`'s guard/plan/synth figures for
# guardrail+think+plan+write (15+15+45+45 = 120s) plus `_QUERY_CLASS_
# BUDGET_S`'s largest figure, `"exploratory"` (120s), for act: 240s
# total. Logged as a build decision, DECISIONS.md, 2026-08-11 (fix round
# 2). On timeout, `MCPError(code=REQUEST_TIMEOUT, ...)` is raised (never
# a hang, never a silent empty response), and unsubscribing happens as an
# ordinary side effect of the exception propagating through `RunRegistry.
# subscribe`'s own `try`/`finally` (verified directly against a
# never-terminating fake stream before this fix landed: `subscriber_
# count` returns to 0 the instant the timeout fires), so the registry's
# existing eviction/abandonment machinery can reclaim the entry rather
# than leaking it.
_FOLD_LOOP_TIMEOUT_S = 240.0

# F-4.1-A-09 (adversary round 1, fix round 2): never interpolate `Error
# Payload.message` into a response an external MCP caller can read. The
# adversary demonstrated a live internal DB host, port, username, and
# database name leaking this way (`_fallback_answer_text`'s previous,
# unsanitized `f"...{error_payload.message}"`). Keyed by `error_class`
# exactly like `core/graph.py`'s own `_STEP_ERROR_END_USER_MESSAGES`
# sanitizes a `HarnessCallError` before it becomes a client-visible
# payload (F-2.0-12's precedent, the closest one this repo has for this
# exact boundary; the REST/SSE surface itself does not yet sanitize
# `ErrorPayload.message`, confirmed by reading `harness/cost_control.py`'s
# `sanitize_event_for_end_user`, which redacts `total_cost_usd` only).
# `"cancelled"` is this surface's own addition, since `_STEP_ERROR_END_
# USER_MESSAGES` only covers the three `HarnessCallError`-derived classes
# and a cancellation (`error_class="cancelled"`, added at build phase 4.0
# for `F-4.0-A-04`) is not one of those.
_MCP_FATAL_ERROR_DISCLOSURE: dict[str, str] = {
    "transient": "This query hit a temporary error before finishing. Retrying may succeed.",
    "recoverable": "This query could not complete as requested.",
    "unexpected": "This query failed unexpectedly before finishing.",
    "cancelled": "This query was stopped before it finished.",
}


def _fatal_error_disclosure(error_payload: ErrorPayload) -> str:
    """Sanitized, external-facing sentence for a fatal `ErrorPayload`,
    keyed by `error_class` (F-4.1-A-09). `error_class` is a closed
    four-value `Literal` (`contracts.events.ErrorPayload`), so the
    `"unexpected"` fallback below is defensive completeness, never
    reachable today.
    """
    return _MCP_FATAL_ERROR_DISCLOSURE.get(
        error_payload.error_class, _MCP_FATAL_ERROR_DISCLOSURE["unexpected"]
    )

# F-4.1-A-13 (adversary round 1, fix round 2): the SDK's own auto-derived
# argument model (`func_metadata()`, read from the installed wheel) sets
# no stricter-than-default Pydantic config and exposes no parameter to
# request one, so an unknown top-level tool-call argument is silently
# dropped rather than rejected (Pydantic's default `extra="ignore"`).
# This is the flat input schema's own three declared names, restated here
# once rather than derived from the function signature at import time, to
# keep `_reject_unknown_arguments` a small, obviously-correct check.
_ALLOWED_TOOL_ARGUMENT_NAMES = frozenset({"query", "audience_depth", "session_id"})

# F-4.1-A-16 (adversary round 1, fix round 2): C0 control bytes and DEL,
# including the ESC (\x1b) that opens an ANSI escape sequence and the NUL
# (\x00) an adversary used to build a length-legal but hostile `query`.
# Tab, newline, and carriage return are excluded from the pattern (a real
# question can legitimately contain them) and are never rejected.
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _reject_control_bytes(value: str) -> str:
    """`AfterValidator` for the `query` parameter (F-4.1-A-16): raises on
    the first C0/DEL control byte found, applied by the SDK's own
    `func_metadata()`-derived argument model exactly the way `Field(max_
    length=2000)` on the same parameter already is (both are `Annotated`
    metadata on one parameter; `func_metadata()` preserves the caller's
    full original annotation, verified directly against the installed
    wheel before relying on it), never a second validation pass this
    module runs by hand.
    """
    if _CONTROL_CHAR_PATTERN.search(value):
        raise ValueError("query must not contain control characters")
    return value


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

    F-4.1-A-11 (adversary round 1, fix round 2): a genuine duplicate
    `Authorization` header (two distinct values on the same request, not
    a casing variant, which Starlette's `Headers.get` already merges
    case-insensitively) is rejected outright rather than resolved
    first-wins, since this surface has no way to know whether a fronting
    proxy authorizes on the first value, the last value, or rejects the
    request itself; picking one silently would be a confused-deputy risk
    for whichever caller assumed the other convention. `Context.headers`
    is Starlette's own `Headers` type in every HTTP-driven case this
    server handles (confirmed directly against the installed `mcp==2.0.0`
    wheel: `type(ctx.headers).__mro__` includes `starlette.datastructures.
    Headers`), so `getlist` is available whenever there is a real
    duplicate to detect; the `hasattr` guard is defensive only, for a
    hypothetical non-HTTP transport whose header mapping does not support
    multi-value lookup.
    """
    headers = ctx.headers
    if headers is None:
        return None
    if hasattr(headers, "getlist") and len(headers.getlist("authorization")) > 1:
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

    F-4.1-A-14 (adversary round 1, fix round 2): the missing-header and
    malformed-scheme checks need no database at all, so they run before
    `session_scope()` opens a pooled connection, rather than inside it.
    `has_bearer_scheme` is the exact same check `resolve_user_from_bearer_
    token` runs first, reused rather than duplicated (F-4.1-A-12's fix,
    same helper); this is a cheap, redundant short-circuit for the common
    no-header/malformed-header rejection, never a second implementation of
    the token/user lookup itself, which still runs, unchanged, below.
    """
    authorization = _extract_bearer_header(ctx)
    if not has_bearer_scheme(authorization):
        raise MCPError(code=INVALID_REQUEST, message=_AUTH_FAILURE_MESSAGE)
    with session_scope() as session:
        try:
            return resolve_user_from_bearer_token(authorization, session)
        except InvalidBearerTokenError:
            raise MCPError(code=INVALID_REQUEST, message=_AUTH_FAILURE_MESSAGE) from None


def _reject_unknown_arguments(ctx: Context) -> None:
    """F-4.1-A-13 (adversary round 1, fix round 2): reject a tool call
    carrying an argument this tool does not declare, before it is
    silently dropped.

    The SDK's own auto-derived argument model (`func_metadata()`, read
    from the installed wheel) sets no stricter-than-default Pydantic
    config and exposes no parameter to request one, so Pydantic's default
    `extra="ignore"` applies: a caller sending `operator_mode: true` or
    `user_id: "..."` alongside `query` gets back a normal success
    response with no signal its extra argument was ignored rather than
    honored. Neither name has any effect on this surface today
    (`operator_mode` is hard-pinned in code below, `user_id` comes from
    the bearer token), so this is not a privilege-escalation path; a
    protocol success response should still never imply an argument was
    honored when it was silently discarded.

    `ctx.request_context.params["arguments"]` is the raw JSON-RPC `tools/
    call` arguments mapping AS SENT, before the SDK's own arg model has
    stripped anything (confirmed directly against the installed `mcp==
    2.0.0` wheel: `ServerRequestContext.params` is the literal request
    params the transport received, `mcp/server/runner.py`'s `_make_
    context`). This is the one point in the request lifecycle this
    surface can still see what the caller actually sent. Defensive:
    absent or non-dict `params`/`arguments` (a shape this SDK does not
    produce for a `tools/call` request today, but not provably
    impossible for a future transport) is treated as "nothing to check"
    rather than raised on, since this function's only job is to catch an
    UNEXPECTED key, never to re-validate a shape `func_metadata()` already
    owns.
    """
    request_context = ctx.request_context
    params = request_context.params if request_context is not None else None
    arguments = params.get("arguments") if params else None
    if not isinstance(arguments, dict):
        return
    unknown = set(arguments) - _ALLOWED_TOOL_ARGUMENT_NAMES
    if unknown:
        raise MCPError(
            code=INVALID_PARAMS,
            message=f"unknown argument(s): {', '.join(sorted(unknown))}",
        )


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

    F-4.1-A-09 (adversary round 1, fix round 2): the error branch below
    used to interpolate `error_payload.message` verbatim, which is
    internal text (a raw exception string in at least one real emitter,
    `core/graph.py`'s daily-cap decline path) never meant for an external
    caller. It now returns `_fatal_error_disclosure`'s sanitized,
    `error_class`-keyed sentence instead, never the raw message.
    """
    if guard_payload is not None and not guard_payload.passed:
        reason_suffix = f" ({guard_payload.reason})" if guard_payload.reason else ""
        return (
            "This question could not be answered: it did not pass this "
            f"system's content guardrail{reason_suffix}."
        )
    if error_payload is not None:
        return _fatal_error_disclosure(error_payload)
    return "This query could not be completed: the run ended before producing an answer."


# Tri-state floor for `TrustSignalPayload.triangulated` (F-4.1-A-02):
# False (ran, did not concord) is worse than None (not evaluated), which
# is worse than True (ran, concords). Mirrors `synthesis.trust`'s own
# `_SEVERITY` floor-by-min pattern for `TrustOutcome`, applied to this
# field's own three-value domain instead of reimporting a table shaped
# for a different type.
_TRIANGULATION_SEVERITY: dict[bool | None, int] = {False: 0, None: 1, True: 2}


def _aggregate_claim_trust_signals(
    claim_signals: list[TrustSignalPayload],
    terminal_trust_outcome: Literal["answer", "flag", "ask", "refuse"] | None,
) -> TrustSignalPayload:
    """F-4.1-A-02 (adversary round 1, fix round 2): synthesize an
    answer-scope `trust_signal` from claim-scoped ones only, for a run
    that emitted `trust_signal` events but never an answer-scope one.

    Previously this shape fell through to the same fixed, cheerful
    default the fully-silent case uses (`risk_tier="low"`, `grounded=
    True`), which the adversary demonstrated actively CONTRADICTS the
    claim-level verdicts it discards: two `flag`/`high`/ungrounded/
    non-triangulated claims produced a top-level `outcome: "answer",
    risk_tier: "low", grounded: true`, the exact inversion Section
    8.3.4's most-restrictive-wins rule exists to prevent. Every field
    here floors at the worst claim-scoped verdict instead:

    - `outcome`: `synthesis.trust.aggregate`, the same function `core/
      graph.py`'s own write_node uses for the identical most-restrictive-
      claim-wins rule (F-3.4-A-01's precedent), reused verbatim rather
      than reimplemented. `terminal_trust_outcome` is the `default` only,
      used if `claim_signals` were somehow empty (never true where this
      function is actually called, guarded by the caller).
    - `risk_tier`: `RiskTier` is a strict two-value `Literal`
      (`synthesis.trust.RiskTier`), so "high" if any claim is "high",
      else "low".
    - `grounded`: False if any claim is ungrounded.
    - `triangulated`: the worst of the tri-state via `_TRIANGULATION_
      SEVERITY` above.
    """
    outcomes = [signal.outcome for signal in claim_signals]
    resolved_outcome = aggregate(outcomes, default=terminal_trust_outcome or "refuse")
    risk_tier: Literal["low", "high"] = (
        "high" if any(signal.risk_tier == "high" for signal in claim_signals) else "low"
    )
    grounded = all(signal.grounded for signal in claim_signals)
    triangulated_values = [signal.triangulated for signal in claim_signals]
    triangulated = min(triangulated_values, key=lambda value: _TRIANGULATION_SEVERITY[value])
    return TrustSignalPayload(
        outcome=resolved_outcome,
        risk_tier=risk_tier,
        grounded=grounded,
        triangulated=triangulated,
        citation_id=None,
        scope="answer",
    )


def _floor_trust_signal_for_fatal_error(trust_signal: TrustSignalPayload) -> TrustSignalPayload:
    """F-4.1-A-01 / F-4.1-A-05 (adversary round 1, fix round 2): a fatal
    error interrupted the run (including a cancellation, `error_class=
    "cancelled"`), so whatever partial answer text exists cannot be
    vouched for as complete or grounded. Floors, never raises:

    - `outcome`: no better than `"flag"` (`synthesis.trust.aggregate`,
      Section 8.3.4's most-restrictive-wins rule, reused verbatim). A
      `"refuse"`/`"ask"` outcome the run itself already reported stays
      exactly that, since both already outrank `"flag"`.
    - `grounded`: forced `False`. Text cut short by a crash cannot be
      vouched for as fully supported by whatever citations arrived
      before the cut.
    - `risk_tier`: forced `"high"`.

    Repro this closes (F-4.1-A-01): a stream emitting a partial clinical
    `token`, a citation, an answer-scope `trust_signal(outcome="answer")`,
    then a fatal `error`, used to fold to `answer="Tamoxifen is
    contraindicated"` (the qualifying clause never arrived) with
    `outcome: "answer", risk_tier: "low", grounded: True, is_error:
    False`: a truncated clinical statement whose truncation inverts its
    meaning, presented as complete and grounded.
    """
    return trust_signal.model_copy(
        update={
            "outcome": aggregate([trust_signal.outcome, "flag"]),
            "grounded": False,
            "risk_tier": "high",
        }
    )


def _truncate_on_word_boundary(text: str, max_length: int) -> str:
    """Truncate `text` to at most `max_length` characters, preferring the
    last whitespace boundary within the cap over a hard mid-word cut
    (F-4.1-A-04's secondary ask). Falls back to a hard cut when no
    boundary exists in at least the back half of the budget, so a single
    anomalously long token cannot collapse the answer to a sliver.
    """
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip()


def _merge_disclosure_messages(existing: str | None, notes: list[str]) -> str:
    """Fold `notes` (F-4.1-A-01/04/05/08's disclosure sentences) into
    `trust_signal.message`, appending to whatever was already there
    (Section 8.4's refuse payload may already carry one) rather than
    overwriting it, then hard-caps at `TrustSignalPayload.message`'s own
    500-char `max_length` so a combination of disclosures can never fail
    that field's own validation.
    """
    parts = ([existing] if existing else []) + notes
    return " ".join(parts)[:500]


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
    event (there is at most one; `citation`-scoped ones are per-claim,
    collected separately below rather than discarded, since Section
    13.2's output carries one `trust_signal` object, not a list, and
    F-4.1-A-02's fix needs them to build an honest fallback) becomes
    `trust_signal`.

    Some terminal shapes emit no answer-scope `trust_signal` event at all
    (the no-tool-selected path in `write_node`, and every early-exit path
    that never reaches `write_node`), so a synthetic one is built from
    whatever claim-scoped signals arrived (F-4.1-A-02), or from the
    terminal `done` event's `trust_outcome` when neither an answer-scope
    nor any claim-scope signal was observed. This guarantees Section
    13.2's "all four output fields required" even on a run shape that
    never itself emits a per-run `trust_signal` event.

    F-4.1-A-06 (adversary round 1, fix round 2): the event-consuming loop
    is wrapped in `asyncio.timeout(_FOLD_LOOP_TIMEOUT_S)`, a wall-clock
    bound this surface owns on top of every per-step timeout already
    enforced inside the run. On timeout, `MCPError(code=REQUEST_TIMEOUT)`
    is raised; `RunRegistry.subscribe`'s own `try`/`finally` still runs as
    the timeout's `CancelledError` propagates through it, so `subscriber_
    count` returns to its pre-call value and the registry's existing
    eviction/abandonment machinery can still reclaim the entry (verified
    directly against a never-terminating fake stream before this fix
    landed).
    """
    answer_parts: list[str] = []
    citations: list[CitationPayload] = []
    citation_events_seen = 0
    answer_trust_signal: TrustSignalPayload | None = None
    claim_trust_signals: list[TrustSignalPayload] = []
    terminal_trust_outcome: Literal["answer", "flag", "ask", "refuse"] | None = None
    guard_payload: GuardPayload | None = None
    fatal_error_payload: ErrorPayload | None = None

    try:
        async with asyncio.timeout(_FOLD_LOOP_TIMEOUT_S):
            async for event in default_registry.subscribe(run_id, after_seq=-1):
                if event.type == "token":
                    answer_parts.append(TokenPayload(**event.payload).text)
                elif event.type == "citation":
                    citation_events_seen += 1
                    if len(citations) < _MAX_CITATIONS:
                        citations.append(CitationPayload(**event.payload))
                elif event.type == "trust_signal":
                    candidate = TrustSignalPayload(**event.payload)
                    if candidate.scope == "answer":
                        answer_trust_signal = candidate
                    elif candidate.scope == "claim":
                        claim_trust_signals.append(candidate)
                elif event.type == "guard":
                    guard_payload = GuardPayload(**event.payload)
                elif event.type == "error":
                    payload = ErrorPayload(**event.payload)
                    if payload.fatal:
                        fatal_error_payload = payload
                elif event.type == "done":
                    terminal_trust_outcome = DonePayload(**event.payload).trust_outcome
                # "think", "plan", "tool_start", "tool_result", and "cost"
                # carry nothing this response's schema has a field for;
                # discarded by simply not matching any branch above.
    except TimeoutError:
        raise MCPError(
            code=REQUEST_TIMEOUT,
            message=(
                f"this query exceeded the MCP surface's {_FOLD_LOOP_TIMEOUT_S:.0f}s "
                "wall-clock budget and was aborted before finishing; retry with a "
                "narrower question, or use the REST/SSE surface to watch the run's "
                "own event stream instead of waiting for one final result"
            ),
        ) from None

    if answer_trust_signal is None:
        if claim_trust_signals:
            answer_trust_signal = _aggregate_claim_trust_signals(
                claim_trust_signals, terminal_trust_outcome
            )
        else:
            resolved_outcome = terminal_trust_outcome or "refuse"
            answer_trust_signal = TrustSignalPayload(
                outcome=resolved_outcome,
                # T-4.3-05, build phase 4.3: closes F-4.1-J3-02, the
                # residual F-4.1-A-03 fix round 2 left carried open. This
                # is the fully-silent fallback branch: no `trust_signal`
                # event of any scope arrived, so no risk assessment ran,
                # and "low" was a fixed, unearned assertion in exactly
                # the same shape the refusal sites in `core/graph.py`
                # had. F-4.1-J3-02 carried this open because `synthesis.
                # trust.RiskTier` (the internal `ClaimTrust` dataclass's
                # type) is a strict two-value `Literal["low", "high"]`
                # with no "unknown" member, and asserting "high" would
                # have been its own unearned assertion in the opposite
                # direction. That blocker does not apply here:
                # `TrustSignalPayload.risk_tier` (contracts/events.py) is
                # a bare `str`, not `RiskTier`, so "unknown" is a valid
                # wire value without widening any type, the same fix
                # made in `core/graph.py`'s two refusal sites this same
                # phase.
                risk_tier="unknown",
                # F-4.1-A-03: `grounded` must reflect whether a citation
                # actually exists, never be asserted from the outcome
                # alone. Zero citations means nothing here was verified,
                # regardless of what `trust_outcome` the run reported.
                grounded=bool(citations) and resolved_outcome == "answer",
                triangulated=None,
                citation_id=None,
                scope="answer",
            )

    raw_answer_text = "".join(answer_parts).strip()
    answer_text = raw_answer_text
    if not answer_text:
        answer_text = _fallback_answer_text(
            guard_payload=guard_payload, error_payload=fatal_error_payload
        )

    disclosures: list[str] = []

    if len(answer_text) > _MAX_ANSWER_LENGTH:
        answer_text = _truncate_on_word_boundary(answer_text, _MAX_ANSWER_LENGTH)
        disclosures.append(
            f"The answer above was truncated to this surface's {_MAX_ANSWER_LENGTH}-"
            "character limit; some content was omitted."
        )

    if citation_events_seen > _MAX_CITATIONS:
        omitted = citation_events_seen - _MAX_CITATIONS
        disclosures.append(
            f"{omitted} citation(s) beyond this surface's {_MAX_CITATIONS}-citation "
            "limit were omitted; some citation markers in the answer above may not "
            "resolve to a returned citation."
        )

    if fatal_error_payload is not None:
        answer_trust_signal = _floor_trust_signal_for_fatal_error(answer_trust_signal)
        disclosures.append(_fatal_error_disclosure(fatal_error_payload))

    if disclosures:
        answer_trust_signal = answer_trust_signal.model_copy(
            update={
                "message": _merge_disclosure_messages(answer_trust_signal.message, disclosures)
            }
        )

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
    query: Annotated[str, Field(max_length=2000), AfterValidator(_reject_control_bytes)],
    ctx: Context,
    audience_depth: Literal["clinical_brief", "researcher", "deep_technical"] = "researcher",
    session_id: Annotated[str | None, Field(max_length=64)] = None,
) -> AskBiomedicalQuestionOutput:
    """The one MCP tool this server advertises (Section 13.2).

    Auth-first: `_authenticate_mcp_caller` runs before anything else in
    this function body, so a caller with a missing, malformed, or invalid
    bearer token never reaches `RunRegistry.create_run` (T-4.1-03).
    `_reject_unknown_arguments` runs immediately after (F-4.1-A-13,
    adversary round 1, fix round 2), also before `create_run`: rejecting
    an unrecognized argument spends no more budget than rejecting a bad
    token does.

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
    _reject_unknown_arguments(ctx)

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
    # F-4.10-J-04 / F-4.10-A-08: the concurrent-run cap build phase 4.10
    # added to `create_run` reaches this surface too, because with
    # `owner_id` omitted `create_run` derives `user:<uuid>` from
    # `query.user_id`, the same owner string the web surface builds. So a
    # caller holding runs open in a browser tab can hit the cap here.
    # Converted to a structured MCPError like every other failure in this
    # handler, never allowed to escape as a bare RuntimeError.
    try:
        default_registry.create_run(query_obj, context, run_id=run_id)
    except ConcurrentRunCapExceededError as exc:
        # T-4.3-05: branch on the structural `bound` attribute rather than
        # a static message, same reasoning as the REST/SSE catch site.
        # Nothing derived from `str(exc)` reaches the caller, matching
        # F-4.10-J-04's fix on the other surface.
        raise MCPError(
            code=INVALID_REQUEST,
            message=_RUN_CAP_MESSAGES_BY_BOUND.get(exc.bound, _RUN_CAP_MESSAGE),
        ) from None
    return await _fold_run_to_response(run_id)
