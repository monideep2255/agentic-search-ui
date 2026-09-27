"""The outbound-only MCP server: build phase 4.1, `tracker/phase_4.1.md`.

Spec: `requirements/Technical_specification.md` Section 13.2 (the MCP
server, outbound-only), Section 9.1 (`CitationPayload`, referenced not
restated), Decision 24 and the 2026-07-22 Step 2.3-to-Phase-4 decision
(direct Python tools, no inbound MCP; MCP is outbound delivery only).

Exposes four MCP tools since build phase 8.10 (T-8.10-05), on the product
owner's decision of 2026-09-26 in `DECISIONS.md` ("The MCP server gets full
parity with the web app"), which overrules Section 13.2's one advertised
tool for MCP while the specification itself stays locked:

- `ask_biomedical_question`: wraps the SAME core agent loop
  `adapters/web_sse/app.py` already drives (via `RunRegistry.create_run`/
  `RunRegistry.subscribe`), never the seven internal tools directly.
- `list_past_searches`, `reopen_past_answer`, `send_answer_feedback`: the
  MCP faces of `GET /v1/history`, `GET /v1/history/{trace_id}/answer` and
  `POST /v1/query/{run_id}/feedback`, calling the same service functions
  under the same ownership checks.

Request/response, not streaming: the ask tool subscribes to a run's event
stream, waits for the terminal `done` (or a fatal `error`), and folds
everything into one JSON result that extends Section 13.2's schema with
optional fields only. No `plan` or `tool_start` event ever reaches an MCP
caller, and of `think` only the clarifying question and its options do.
`operator_mode` is hard-pinned `False` here regardless of the
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
      tracker/phase_4.1.md's pre-build source read. Also
      mcp.server.transport_security.TransportSecuritySettings, for
      `transport_security_settings()` below.
    - Environment variables MCP_ALLOWED_HOSTS and MCP_ALLOWED_ORIGINS:
      read by `transport_security_settings()`, which the `/mcp` mount in
      adapters/web_sse/app.py passes to `streamable_http_app`. Both
      default to the SDK's own localhost-only lists when unset.
    - system_03_search_agent.auth.dependencies (resolve_user_from_bearer_
      token, has_bearer_scheme, InvalidBearerTokenError): the exact
      decode-then-lookup logic `get_current_user` uses, extracted so this
      non-FastAPI caller can reuse it without duplicating it.
    - system_03_search_agent.contracts.events (CitationPayload,
      DonePayload, ErrorPayload, GuardPayload, ThinkPayload, TokenPayload,
      TrustSignalPayload): the Section 2.3 payload models this module
      folds events against. `CitationPayload` is reused verbatim as
      Section 13.2's `CitationV1`, never redefined.
    - system_03_search_agent.contracts.query (Query, RequestContext): the
      one request shape every surface builds before calling into the core.
    - system_03_search_agent.core.run_registry (default_registry,
      RunNotFoundError, RunNotOwnedError): the SAME registry instance
      `adapters/web_sse/app.py` already uses, and its one ownership rule
      (`resolve_owned_run`). This module never builds a second registry.
    - system_03_search_agent.data.session (session_scope): one DB session
      per tool call, to resolve the caller's bearer token to a `User` row.
    - system_03_search_agent.feedback (record_feedback,
      FeedbackOwnershipError, InteractionNotFound) and
      system_03_search_agent.feedback.contracts (FeedbackCitationFlag):
      the feedback write `POST /v1/query/{run_id}/feedback` calls.
    - system_03_search_agent.feedback.history (list_history,
      get_saved_answer, DEFAULT_LIMIT, MAX_LIMIT): the owner-scoped reads
      `GET /v1/history` and `GET /v1/history/{trace_id}/answer` call.
    - system_03_search_agent.observability.analytics (capture_event,
      AnalyticsEvent): the same best-effort feedback-submitted count the
      REST feedback route fires.
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
      event stream back. `send_answer_feedback` writes the caller's own
      `interactions.user_feedback` through `record_feedback`, the same
      function and the same row-level ownership check the REST route uses.

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
import logging
import os
import re
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_PARAMS, INVALID_REQUEST, REQUEST_TIMEOUT, ToolAnnotations
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

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
    ThinkPayload,
    TokenPayload,
    TrustSignalPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.persona import persona_for_session
from system_03_search_agent.core.run_registry import (
    ConcurrentRunCapExceededError,
    RunNotFoundError,
    RunNotOwnedError,
    default_registry,
)
from system_03_search_agent.data.models import User
from system_03_search_agent.data.session import session_scope
from system_03_search_agent.feedback import (
    FeedbackOwnershipError,
    InteractionNotFound,
    record_feedback,
)
from system_03_search_agent.feedback.contracts import FeedbackCitationFlag
from system_03_search_agent.feedback.history import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    get_saved_answer,
    list_history,
)
from system_03_search_agent.observability.analytics import AnalyticsEvent, capture_event
from system_03_search_agent.synthesis.trust import aggregate

logger = logging.getLogger(__name__)

# Section 13.2's locked output_schema: `citations` maxItems 50, `answer`
# maxLength 8000. Applied twice: once as the Pydantic field constraint
# (so a malformed internal fold would fail loudly rather than ship a
# non-conforming response) and once defensively while folding (see
# `_fold_run_to_response`), the same belt-and-suspenders pattern
# `adapters/web_sse/app.py`'s `_MAX_CITATIONS_PER_RUN` already uses.
#
# T-8.10-05 raised the citation cap from 50 to 100, under the product
# owner's parity decision of 2026-09-26 (`DECISIONS.md`). What a person saw
# before: a long answer such as Marfan syndrome's cited 85 records on this
# surface and 93 on the web, this one returned the first 50, and the answer
# text still pointed at markers such as [77] that resolved to nothing.
#
# WHY 100 AND NOT ANOTHER NUMBER. The event contract puts no count on one
# answer's citations: every citation is its own `citation` event, and
# `contracts/events.py` bounds each event's fields, never how many there
# are. The run does bound them. `write_node` builds one citation per
# display slot, and the slots come from `build_synth_findings`, capped at
# `core/graph.py`'s `_MAX_FINDINGS_FOR_DISPLAY`, which is the planned graph
# call's own `_PLAN_TOOL_CALL_ROW_LIMIT`, 100. So 100 is the most one
# answer can carry, and this cap keeps every one of them while still being
# a bound, as `production-standards.md`'s multi-agent pipeline gate
# requires. Held as a literal here rather than imported, so the published
# output schema moves only by a deliberate edit, and pinned to the run's
# own bound by `test_the_citation_cap_is_the_runs_own_bound`, which fails
# the day the run's bound rises past this one.
_MAX_CITATIONS = 100
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

# The same check's declared names for the three tools T-8.10-05 added, one
# set per tool, so an argument one tool takes is never silently accepted by
# another.
_LIST_PAST_SEARCHES_ARGUMENT_NAMES = frozenset({"limit"})
_REOPEN_PAST_ANSWER_ARGUMENT_NAMES = frozenset({"trace_id"})
_SEND_ANSWER_FEEDBACK_ARGUMENT_NAMES = frozenset(
    {"run_id", "rating", "comment", "flagged_reason", "citation_flags"}
)

# T-8.10-05: every depth the web offers. `plain_language` is the web's own
# default; this surface's default stays `researcher`, so an existing client
# that names no depth gets exactly the answers it got before (the ledger's
# "Decisions this plan takes"). Listed in the same order as
# `contracts.query.Query.audience_depth`'s own Literal.
AudienceDepth = Literal["plain_language", "researcher", "clinical_brief", "deep_technical"]
_DEFAULT_AUDIENCE_DEPTH: AudienceDepth = "researcher"

# The fixed, caller-safe messages the three new tools raise, never built
# from an exception or a stored value. Each says what the REST route it
# stands in for says. The not-found one adds what to do next, because REST's
# bare "no such run" leaves an agent that took a trace_id from
# `list_past_searches` with nothing to act on: the registry holds a finished
# run only for its retention window, and REST's own feedback route records
# that gap as known rather than routing around it.
_NO_SUCH_RUN_MESSAGE = (
    "no such run: feedback can be sent for a run_id that ask_biomedical_question "
    "returned to this account while that run is still held on the server"
)
_NOT_YOUR_RUN_MESSAGE = "you do not own this run"
_FEEDBACK_NOT_YET_CAPTURED_MESSAGE = (
    "this run's interaction row has not been captured yet; capture runs as a "
    "background task right after the answer finishes, so retry this exact "
    "request in a few seconds"
)
_NO_SAVED_ANSWER_MESSAGE = "no saved answer for this search; ask it again to get a fresh one"
# Build phase 8.10's fix round, F-8.10-A08: a call carrying none of the four
# was recorded as feedback and could replace an earlier rating with nothing.
_NOTHING_TO_RECORD_MESSAGE = (
    "nothing to record: send at least one of rating ('up' or 'down'), comment, "
    "flagged_reason or citation_flags. Any feedback already sent for this answer "
    "is unchanged"
)

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
    # F-4.5-A-21: MCP was the one delivery surface build phase 4.5 left
    # without a persona, though the phase's own ticket said all four.
    #
    # Optional rather than required, and that is load-bearing twice over:
    # Section 13.2's locked `output_schema` names four required fields, so
    # widening the required set would change the locked shape rather than
    # extend it, and `system-design-patterns` pattern 10 permits a new
    # OPTIONAL field within v1 and nothing more.
    #
    # Adding a key here also required adding it to `_ALLOWED_RESPONSE_KEYS`
    # in the phase 4.1 premise gate, which pins the resolved key set of the
    # whole response tree so that any unlisted key fails, including a
    # renamed cost field. That allowlist is a deliberate manual control, so
    # this addition was approved by the product owner on 2026-08-20 rather
    # than made to get a test green: the value is a server-side name drawn
    # from a checked-in file of deceased scientists, carrying no user data,
    # no cost data and no identifier.
    persona_name: str | None = Field(default=None, max_length=64)
    # T-8.10-05, four more optional fields, under the same two constraints
    # as `persona_name` above: optional, so Section 13.2's four required
    # fields stay exactly as they were, and each one added to the pinned
    # `_ALLOWED_RESPONSE_KEYS` in `tests/.../adapters/mcp/
    # test_no_cost_and_auth.py` under the product owner's parity decision
    # of 2026-09-26, which named what these carry. None of them is a cost,
    # a credential or another account's data: each is either the caller's
    # own conversation id or text the web app already shows that caller.
    session_id: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "The conversation this answer belongs to. Pass it back as session_id "
            "on the next ask_biomedical_question call to ask a follow-up, so "
            "'it' or 'that gene' refers to what was just discussed."
        ),
    )
    # `DonePayload.trust_line`, the one plain sentence the web shows under
    # an answer ("Based on 3 sources, not yet confirmed"), same bound.
    trust_line: str | None = Field(
        default=None,
        max_length=200,
        description="The one plain sentence about how far this answer can be trusted, as the web app shows it.",
    )
    # `ThinkPayload.clarifying_question` and `.clarifying_options`, same
    # bounds, set only when this answer is a question back to the caller
    # (see `_fold_run_to_response`). The question also arrives as `answer`,
    # and is carried here too because `trust_signal.outcome == "ask"` alone
    # is ambiguous: the trust table uses `ask` for a hedged answer as well
    # (`synthesis.trust.DECISION_TABLE`), and the web keeps the two apart by
    # the same field (`useRunView.ts`, `clarification`).
    clarifying_question: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Set when the answer is a question back to you rather than an answer. "
            "Reply with one of clarifying_options, or your own words, as the next "
            "query with the same session_id."
        ),
    )
    clarifying_options: list[Annotated[str, Field(max_length=220)]] | None = Field(
        default=None,
        max_length=4,
        description="Ready-made questions to send next when clarifying_question is set, or null.",
    )


class PastSearch(BaseModel):
    """One of the caller's own past searches: `GET /v1/history`'s
    `HistoryItem`, field for field and bound for bound, restated here
    rather than imported because `adapters/web_sse/app.py` imports this
    module, so the reverse import would be circular."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(..., max_length=64)
    question: str = Field(..., max_length=2000)
    asked_at: datetime
    trust_signal: str = Field(..., max_length=20)
    citation_count: int = Field(..., ge=0)
    has_saved_answer: bool = False


class PastSearchesOutput(BaseModel):
    """`GET /v1/history`'s `HistoryResponse`, field for field: `count` is
    the size of this page, never a total, and `omitted_count` is how many
    of the caller's own rows were withheld because they could not be shown
    honestly (the REST route's own reasons, applied by the same guard)."""

    model_config = ConfigDict(extra="forbid")

    items: list[PastSearch] = Field(default_factory=list, max_length=MAX_LIMIT)
    count: int = Field(..., ge=0)
    omitted_count: int = Field(0, ge=0)


class ReopenedAnswerOutput(BaseModel):
    """One past answer, as `GET /v1/history/{trace_id}/answer` returns it.

    Two deliberate differences from the REST shape, both in the caller's
    favour and neither a new fact:

    - `audience_depth` reports the stored depth as one of the four values
      `ask_biomedical_question` takes, so an agent can ask again at the same
      depth. REST folds three of them onto `researcher` only because its
      pinned wire contract declares two values.
    - `citations` are validated one by one as `CitationPayload`, and any
      stored entry that no longer validates is left out and counted in
      `citations_omitted`, never published half-formed and never allowed
      to fail the whole answer (REST drops a non-dict entry the same way).
      A marker in `answer_markdown` that no stored citation answers is
      counted there too (`_reopened_citations`), so the count says how many
      of the answer's markers point at nothing here.
    """

    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(..., max_length=64)
    question: str = Field(..., max_length=2000)
    asked_at: datetime
    audience_depth: AudienceDepth
    answer_markdown: str = Field(..., max_length=32000)
    citations: list[CitationPayload] = Field(default_factory=list, max_length=_MAX_CITATIONS)
    citations_omitted: int = Field(0, ge=0)
    trust_signal: str = Field(..., max_length=20)
    trust_line: str | None = Field(default=None, max_length=200)


class FeedbackRecordedOutput(BaseModel):
    """What `send_answer_feedback` returns once the feedback is stored.
    REST answers 204 with no body; a tool must return something, so it
    returns the run it rated and that the write happened."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., max_length=64)
    recorded: bool


server = MCPServer(
    name="system3-biomedical-search",
    version="1.0.0",
    instructions=(
        "Ask a biomedical research question with ask_biomedical_question. It "
        "returns a cited answer assembled from the NCBI knowledge graph and "
        "live NCBI APIs, or an honest refusal. To ask a follow-up, pass back "
        "the session_id the previous answer returned. When clarifying_question "
        "is set, the answer is a question back to you: reply with one of "
        "clarifying_options. list_past_searches, reopen_past_answer and "
        "send_answer_feedback read your own past searches, reopen a saved "
        "answer, and rate an answer."
    ),
)


# ---------------------------------------------------------------------------
# Transport security: which `Host` and `Origin` headers this surface admits.
# ---------------------------------------------------------------------------
#
# R17, fix set 5 item 5.3, 2026-09-13. Every request to the deployed `/mcp`
# endpoint was refused with `421 Invalid Host header`, signed in or not.
#
# THE CAUSE, confirmed by reading the installed wheel rather than inferred.
# `mcp==2.0.0`'s `MCPServer.streamable_http_app()` takes `host: str =
# "127.0.0.1"` and forwards it to `Server.streamable_http_app()`
# (`mcp/server/lowlevel/server.py` lines 720 to 745), which contains:
#
#     if transport_security is None and host in ("127.0.0.1", "localhost", "::1"):
#         transport_security = TransportSecuritySettings(
#             enable_dns_rebinding_protection=True,
#             allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
#             allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
#         )
#
# `adapters/web_sse/app.py` passed neither argument, so BOTH defaults
# applied: the auto-enable branch fired and built a localhost-only
# allowlist. `TransportSecurityMiddleware._validate_host`
# (`mcp/server/transport_security.py` lines 43 to 63) then matched the
# deployed hostname against that list, failed, and
# `validate_request` returned `Response("Invalid Host header",
# status_code=421)` at line 109, before any handler, any auth check and any
# run. A public hostname could never have matched.
#
# THE FIX KEEPS THE PROTECTION ON and configures the allowlist, rather than
# passing a non-localhost `host` (which would leave `transport_security`
# None and disable the check outright) or constructing
# `TransportSecuritySettings(enable_dns_rebinding_protection=False)`.
# Reasoning recorded here because the cheaper option is the tempting one:
# DNS rebinding aims a victim's own browser at a server the attacker cannot
# otherwise route to, which is a localhost-development threat far more than
# a public-HTTPS one, so switching it off for this deployment would be
# defensible. It is still not free. The `Host` allowlist is also the control
# that stops this API from answering on an unintended hostname, and
# `allowed_origins` is the only same-origin check in front of a
# bearer-authenticated JSON-RPC surface. An allowlist costs one environment
# variable per deployment and keeps both; `attack-the-constraint` says fix
# the configuration gap, not the control that exposed it.
#
# UNSET FAILS CLOSED, NOT OPEN. With neither variable set, this returns the
# SDK's own localhost lists verbatim, so nothing about local development or
# the test suite changes and a deployment that forgets the variable is
# refused loudly rather than opened to every hostname.
_ENV_MCP_ALLOWED_HOSTS = "MCP_ALLOWED_HOSTS"
_ENV_MCP_ALLOWED_ORIGINS = "MCP_ALLOWED_ORIGINS"

# Copied from `mcp/server/lowlevel/server.py`'s auto-enable branch, quoted
# above. Kept as literals rather than imported: the SDK exposes them only
# inside that function body, so there is nothing to import, and pinning them
# here means an SDK upgrade that narrows them cannot silently narrow this
# surface's unset default too.
_SDK_DEFAULT_ALLOWED_HOSTS: tuple[str, ...] = ("127.0.0.1:*", "localhost:*", "[::1]:*")
_SDK_DEFAULT_ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://127.0.0.1:*",
    "http://localhost:*",
    "http://[::1]:*",
)

# A `Host` header value: a DNS name, an IPv4 literal, or a bracketed IPv6
# literal, with an optional port. `:*` is the SDK's own any-port wildcard
# (`_validate_host`'s `allowed.endswith(":*")` branch) and is accepted here
# so an operator can express it; a bare `*` is NOT, see `_parse_host_entry`.
#
# THE TWO SPELLINGS DO NOT COVER EACH OTHER, which is the trap worth naming
# because a configuration that looks right still 421s. `_validate_host` tries
# exact equality first and only then the `:*` suffix, so `example.test` does
# not admit `example.test:443` and `example.test:*` does not admit the bare
# `example.test`. Whether a proxy forwards a port is the proxy's business,
# so `env.example` tells an operator to list each hostname in BOTH spellings.
# Pinned by `test_the_value_env_example_recommends_admits_both_spellings`.
_HOST_PATTERN = re.compile(
    r"^(?:\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?::(?:\*|[0-9]{1,5}))?$"
)
_ORIGIN_SCHEMES = ("http://", "https://")


class MCPTransportSecurityConfigError(ValueError):
    """`MCP_ALLOWED_HOSTS` or `MCP_ALLOWED_ORIGINS` is set to a value this
    surface cannot honour.

    Raised at import time of `adapters/web_sse/app.py`, so the process
    refuses to start rather than serving with a silently empty or silently
    wide allowlist. That direction is deliberate: an empty `allowed_hosts`
    with protection on refuses EVERY request, which is a 421 on every call
    with nothing in the logs pointing at the variable, and R17 was exactly
    that failure once already.
    """


def _parse_host_entry(entry: str, env_name: str) -> str:
    """Validate one comma-separated `Host` allowlist entry."""
    if entry == "*":
        # Rejected rather than passed through, and this is the one arm most
        # likely to be read as over-strict. The SDK matches a wildcard only
        # as a `host:*` SUFFIX, so a bare `*` is compared for exact equality
        # against the Host header, never matches, and refuses everything
        # while the operator who typed it believes they allowed everything.
        # It fails closed, so it is safe, and silent plus safe plus wrong is
        # still a 421 nobody can explain.
        raise MCPTransportSecurityConfigError(
            env_name + " contains a bare '*', which allows nothing rather "
            "than everything: the MCP SDK matches a wildcard only as a "
            "'host:*' port suffix. List each hostname explicitly, for "
            "example 'api.example.com,localhost:*'."
        )
    if not _HOST_PATTERN.match(entry):
        raise MCPTransportSecurityConfigError(
            env_name + " contains an entry that is not a Host header value: "
            + repr(entry)
            + ". Each entry is a hostname with an optional port, for example "
            "'api.example.com' or 'api.example.com:443' or 'localhost:*'. No "
            "scheme, no path, no credentials."
        )
    return entry


def _parse_origin_entry(entry: str, env_name: str) -> str:
    """Validate one comma-separated `Origin` allowlist entry."""
    for scheme in _ORIGIN_SCHEMES:
        if entry.startswith(scheme):
            remainder = entry[len(scheme) :]
            if remainder and _HOST_PATTERN.match(remainder):
                return entry
            break
    raise MCPTransportSecurityConfigError(
        env_name + " contains an entry that is not an origin: "
        + repr(entry)
        + ". Each entry is a scheme plus a host with an optional port and no "
        "trailing path, for example 'https://app.example.com' or "
        "'http://localhost:*'."
    )


def _parse_allowlist(
    raw: str | None,
    env_name: str,
    defaults: tuple[str, ...],
    parse_entry: Callable[[str, str], str],
) -> list[str]:
    """Split one comma-separated allowlist variable, or fall back to `defaults`.

    Unset, or set to whitespace only, yields `defaults`. Set to anything that
    LOOKS like a list but resolves to nothing usable (`","`, `", ,"`) raises
    instead, because that is a typo rather than an intention and quietly
    substituting the localhost defaults for it would reproduce this very
    defect with the variable apparently set.
    """
    if raw is None or not raw.strip():
        return list(defaults)
    entries = [segment.strip() for segment in raw.split(",")]
    if not any(entries):
        raise MCPTransportSecurityConfigError(
            env_name + " is set but lists no entry (found only separators and "
            "whitespace). Unset it to admit localhost only, or list at least "
            "one value."
        )
    parsed: list[str] = []
    for entry in entries:
        if not entry:
            # A trailing or doubled comma in an otherwise valid list. Skipped
            # rather than fatal: the operator's intent is unambiguous and every
            # real entry still had to pass `parse_entry`.
            continue
        value = parse_entry(entry, env_name)
        if value not in parsed:
            parsed.append(value)
    return parsed


def transport_security_settings() -> TransportSecuritySettings:
    """Build the `TransportSecuritySettings` the `/mcp` mount is served with.

    Read fresh on every call, the same convention `harness/cost_control.py`'s
    `_operator_user_ids` and `tools/graph_connection.py`'s `GRAPH_QUERY_URL`
    dispatch already use: a plain `os.environ.get` at the point of use, no
    settings object, no caching. The production call site is
    `adapters/web_sse/app.py`'s module-level `streamable_http_app(...)`, which
    runs exactly once per process, so "fresh" costs nothing there and lets a
    test set the variable and re-read it without reloading a module.

    Raises:
        MCPTransportSecurityConfigError: either variable is set to a value
            that is not a list of Host or Origin values.
    """
    allowed_hosts = _parse_allowlist(
        os.environ.get(_ENV_MCP_ALLOWED_HOSTS),
        _ENV_MCP_ALLOWED_HOSTS,
        _SDK_DEFAULT_ALLOWED_HOSTS,
        _parse_host_entry,
    )
    allowed_origins = _parse_allowlist(
        os.environ.get(_ENV_MCP_ALLOWED_ORIGINS),
        _ENV_MCP_ALLOWED_ORIGINS,
        _SDK_DEFAULT_ALLOWED_ORIGINS,
        _parse_origin_entry,
    )
    # Logged by name: the hostnames this surface admits, which travel in the
    # clear in every request's own `Host` header and are therefore not
    # sensitive, plus the variable each list came from. No credential, no
    # token and no raw environment value is logged here, and the origin list
    # is reported as a count rather than spelled out, since its only job in
    # this line is telling an operator whether it was configured at all.
    logger.info(
        "MCP transport security: DNS-rebinding protection on, allowed hosts "
        "%s (from %s), %d allowed origin(s) (from %s)",
        allowed_hosts,
        _ENV_MCP_ALLOWED_HOSTS,
        len(allowed_origins),
        _ENV_MCP_ALLOWED_ORIGINS,
    )
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
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


def _reject_unknown_arguments(
    ctx: Context, allowed: frozenset[str] = _ALLOWED_TOOL_ARGUMENT_NAMES
) -> None:
    """F-4.1-A-13 (adversary round 1, fix round 2): reject a tool call
    carrying an argument this tool does not declare, before it is
    silently dropped. `allowed` is the calling tool's own declared names
    (T-8.10-05 added three tools); it defaults to the ask tool's.

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
    unknown = set(arguments) - allowed
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


def _is_ask_back(
    *,
    clarifying_question: str | None,
    guard_payload: GuardPayload | None,
    fatal_error_payload: ErrorPayload | None,
    citation_events_seen: int,
) -> bool:
    """Whether this run's answer is a question back to the caller.

    T-8.10-05. What a person saw before: a bare topic such as "GERD" came
    back over MCP as a refusal (`trust_signal.outcome == "refuse"`), the
    same label as "I cannot answer that", with the four one-click options
    the web shows dropped entirely. The core sends an ask-back through the
    refusal path on purpose, and every surface is left to tell the two
    apart; the web does it by the `think` event's `clarifying_question`
    (`frontend/src/hooks/useRunView.ts`, `clarification`), and this is the
    same rule:

    - a `think` event carried a non-empty clarifying question;
    - the guardrail did not refuse the question, since a guardrail refusal
      wins outright on the web too, and its reviewed wording is what a
      refused question must say;
    - no fatal error ended the run, so nothing here is a crash dressed as a
      question;
    - no citation arrived, so this is never used to relabel an answer.
    """
    if clarifying_question is None:
        return False
    if guard_payload is not None and not guard_payload.passed:
        return False
    if fatal_error_payload is not None:
        return False
    return citation_events_seen == 0


async def _fold_run_to_response(
    run_id: str, *, persona_name: str | None = None, session_id: str | None = None
) -> AskBiomedicalQuestionOutput:
    """Drive `run_id` to its terminal event and fold the result into
    Section 13.2's locked response shape.

    Per Section 13.2: "the adapter waits on the internal event stream
    until done, folding think, plan, and tool_start out entirely and
    folding token and tool_result into the final structured response."
    Concretely: `plan`/`tool_start`/`tool_result`/`step`/`cost` events are
    read and discarded (none of them map onto any field this response
    carries); `guard` is kept only to word a guardrail refusal; `think`
    contributes only its clarifying question and options, and `done` its
    verdict and trust line (T-8.10-05); `token` events are concatenated into `answer`
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
    clarifying_question: str | None = None
    clarifying_options: list[str] = []
    trust_line: str | None = None

    try:
        async with asyncio.timeout(_FOLD_LOOP_TIMEOUT_S):
            async for event in default_registry.subscribe(run_id, after_seq=-1):
                if event.type == "think":
                    # T-8.10-05: the first `think` carrying a non-empty
                    # clarifying question is the one the web reads too
                    # (`useRunView.ts` finds the first such event), so a
                    # later one can never swap in a different question.
                    # Trimmed, so a blank question counts as none.
                    if clarifying_question is None:
                        think_payload = ThinkPayload(**event.payload)
                        question = (think_payload.clarifying_question or "").strip()
                        if question:
                            clarifying_question = question
                            clarifying_options = [
                                option.strip()
                                for option in think_payload.clarifying_options or []
                                if option.strip()
                            ]
                elif event.type == "token":
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
                    done_payload = DonePayload(**event.payload)
                    terminal_trust_outcome = done_payload.trust_outcome
                    # T-8.10-05: the trust line the web shows, read the way
                    # the web reads it (trimmed, blank means none).
                    trust_line = (done_payload.trust_line or "").strip() or None
                # "plan", "tool_start", "tool_result", "step" and "cost"
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

    # T-8.10-05: an ask-back is reported as `ask`, never `refuse`. The core
    # emits it through the refusal path, so without this the agent read
    # "GERD" as a topic this system cannot answer. Set to `ask` rather than
    # aggregated with the run's own verdict: `_is_ask_back` already requires
    # zero citations, so no verdict above `ask` can be honest here, and
    # `refuse` is the one this exists to replace. `grounded`, `risk_tier`
    # and `message` are left exactly as the run reported them.
    ask_back = _is_ask_back(
        clarifying_question=clarifying_question,
        guard_payload=guard_payload,
        fatal_error_payload=fatal_error_payload,
        citation_events_seen=citation_events_seen,
    )
    if ask_back:
        answer_trust_signal = answer_trust_signal.model_copy(update={"outcome": "ask"})

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
        persona_name=persona_name,
        session_id=session_id,
        trust_line=trust_line,
        clarifying_question=clarifying_question if ask_back else None,
        clarifying_options=(clarifying_options or None) if ask_back else None,
    )


@server.tool(
    description=(
        "Ask a biomedical research question about genes, variants, diseases, "
        "publications or sequencing records. Returns a cited answer assembled "
        "from the NCBI knowledge graph and live NCBI APIs, or an honest refusal. "
        "Every [n] marker in the answer resolves to an entry in citations. To "
        "ask a follow-up in the same conversation, pass the session_id this "
        "tool returned. When clarifying_question is set, the answer is a "
        "question back to you: send one of clarifying_options, or your own "
        "reply, as the next query with the same session_id."
    )
)
async def ask_biomedical_question(
    query: Annotated[
        str,
        Field(
            max_length=2000,
            description="The question, in plain words, for example 'Which diseases are associated with BRCA1?'.",
        ),
        AfterValidator(_reject_control_bytes),
    ],
    ctx: Context,
    audience_depth: Annotated[
        AudienceDepth,
        Field(
            description=(
                "Who the answer is written for. 'researcher' is the default here; "
                "'plain_language' is the everyday wording the web app uses by "
                "default; 'clinical_brief' and 'deep_technical' are the product's "
                "other two depths."
            )
        ),
    ] = _DEFAULT_AUDIENCE_DEPTH,
    session_id: Annotated[
        str | None,
        Field(
            max_length=64,
            description=(
                "Leave this out to start a new conversation. To ask a follow-up, "
                "pass the session_id a previous answer returned, so 'it' or "
                "'that gene' refers to what was just discussed."
            ),
        ),
    ] = None,
) -> AskBiomedicalQuestionOutput:
    """Ask one question and fold its run into one result (Section 13.2,
    extended additively by T-8.10-05).

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

    T-8.10-05: that session id is now RETURNED, as `session_id`, and the
    input schema says what it is for. Before, an agent had no way to learn
    that follow-ups need one: every call without it started a fresh
    conversation, so "what variants of it are pathogenic?" had no "it".
    Session memory arrived in build phase 4.5, so the id this handler
    mints is a real conversation an agent can continue by passing it back.
    """
    user = await _authenticate_mcp_caller(ctx)
    _reject_unknown_arguments(ctx)

    run_id = str(uuid.uuid4())
    query_obj = Query(
        text=query,
        session_id=session_id if session_id is not None else run_id,
        trace_id=run_id,
        user_id=str(user.id),
        # F-4.5-J-02: the namespaced principal session memory keys on. This
        # surface is registered-accounts-only, so it is always a user
        # principal. Built in the same shape `auth/dependencies.py` mints,
        # since the two must agree for one caller to reach one session row
        # from two surfaces.
        owner_id=f"user:{user.id}",
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
    # F-4.5-A-21: drawn from the same one source every other surface reads,
    # and keyed on the same two values, so a caller reaching this system from
    # MCP and from the web UI in one session sees one name rather than two.
    return await _fold_run_to_response(
        run_id,
        persona_name=persona_for_session(
            session_id=query_obj.session_id, user_id=str(user.id)
        ),
        session_id=query_obj.session_id,
    )


# ---------------------------------------------------------------------------
# History, reopen and feedback: T-8.10-05, the owner's parity decision.
# ---------------------------------------------------------------------------
#
# What a person gets: an AI agent working for them can list the searches
# they made, open an answer they already got without paying for a second
# search, and tell the team an answer was wrong, the same three things the
# web app's history rail and feedback buttons do.
#
# ONE RULE FOR EVERY TOOL BELOW, and it is the REST routes' rule, not a new
# one. The caller is resolved from the bearer token by the same
# `_authenticate_mcp_caller` the ask tool uses, and every read or write is
# scoped by `_owner_id_for(user)`, the namespaced `user:<uuid>` the REST
# routes read off `Principal.owner_id` for the same account. No tool takes
# an owner, a user id or an account from its arguments, so no argument can
# widen what a caller reaches. The service functions then apply their own
# checks exactly as they do for REST:
#
#   - `list_history` and `get_saved_answer` filter on `owner_id` in SQL.
#     Another account's row is never fetched, and `get_saved_answer`
#     answers one `None` for "no such row", "not yours" and "nothing
#     saved", so a stranger learns nothing about a trace id.
#   - Feedback first resolves the run through the registry's one ownership
#     rule, `resolve_owned_run`, as REST's `_get_owned_run` does, then
#     `record_feedback` checks the stored row's owner again under a row
#     lock before any write.
#
# Guests: this surface authenticates registered accounts only
# (`resolve_user_from_bearer_token`), so a guest token is refused before
# any of this runs. A guest gets less here than on REST, never more.


def _owner_id_for(user: User) -> str:
    """The namespaced principal every owner-scoped read and write keys on,
    in the exact shape `auth/dependencies.py` mints for a registered
    account, so this surface and REST reach the same rows for one caller.
    """
    return f"user:{user.id}"


@server.tool(
    description=(
        "List your own past searches, newest first: each one's trace_id, the "
        "question, when it was asked, its trust verdict, how many sources it "
        "cited, and whether its answer can be reopened with reopen_past_answer. "
        "Searches this account made on the web app, the command line or this "
        "server all appear."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
async def list_past_searches(
    ctx: Context,
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=MAX_LIMIT,
            description=f"How many searches to return, 1 to {MAX_LIMIT}. Defaults to {DEFAULT_LIMIT}.",
        ),
    ] = DEFAULT_LIMIT,
) -> PastSearchesOutput:
    """`GET /v1/history` over MCP: `list_history` with the caller's own
    `owner_id`, and the REST handler's own per-row guard, so a row REST
    withholds is withheld here too and counted in `omitted_count`.

    `list_history` is a blocking database read, so it runs in a worker
    thread rather than on the event loop the MCP transport shares.
    """
    user = await _authenticate_mcp_caller(ctx)
    _reject_unknown_arguments(ctx, _LIST_PAST_SEARCHES_ARGUMENT_NAMES)

    entries = await asyncio.to_thread(list_history, owner_id=_owner_id_for(user), limit=limit)
    items: list[PastSearch] = []
    omitted_count = 0
    for entry in entries:
        # The REST handler's two reasons, in its order: a row with no
        # honest citation count (F-4.13-RV-02), and a row that no longer
        # fits this model's bounds (F-4.13-A-02). Either is dropped and
        # counted, never allowed to fail the whole list.
        if entry.citation_count is None:
            omitted_count += 1
            continue
        try:
            items.append(
                PastSearch(
                    trace_id=entry.trace_id,
                    question=entry.question,
                    asked_at=entry.asked_at,
                    trust_signal=entry.trust_signal,
                    citation_count=entry.citation_count,
                    has_saved_answer=entry.has_saved_answer,
                )
            )
        except ValidationError:
            omitted_count += 1
    return PastSearchesOutput(items=items, count=len(items), omitted_count=omitted_count)


# The stored depths this surface reports back as they are. Anything else,
# which only a direct database write could produce, reads back as the
# product's own default, the same floor `get_saved_answer` itself applies.
_STORED_DEPTHS: frozenset[str] = frozenset(
    {"plain_language", "researcher", "clinical_brief", "deep_technical"}
)

#: A citation marker in a saved answer's text, in the screen's own numbers:
#: the `[n]` that `feedback/capture.py`'s `_markers_for` writes and
#: `synthesis/grounding.py`'s `_MARKER` reads.
_ANSWER_MARKER = re.compile(r"\[(\d{1,3})\]")


def _reopened_citations(
    stored_citations: list[Any], answer_markdown: str
) -> tuple[list[CitationPayload], int]:
    """The saved citations `reopen_past_answer` can publish, and how many of
    the answer's citations it cannot.

    `citations_omitted` counts two things, each once:

    - a stored entry left out, past this surface's bound or no longer
      valid as a `CitationPayload`, as before;
    - a marker in `answer_markdown` with no stored entry at all (build
      phase 8.10's fix round, F-8.10-J02 and A02). Capture stores at most
      50 citations (`feedback/capture.py`'s `_MAX_CITATIONS`), so a
      60-marker answer came back pointing [51] to [60] at nothing while
      this said 0. That cap is card 54's; this only stops the count from
      hiding it.

    A marker whose entry was stored but left out is counted by the first
    rule and not again by the second."""
    citations: list[CitationPayload] = []
    left_out = 0
    left_out_indexes: set[int] = set()
    for stored in stored_citations:
        if len(citations) < _MAX_CITATIONS:
            try:
                citations.append(CitationPayload.model_validate(stored))
                continue
            except ValidationError:
                pass
        left_out += 1
        index = stored.get("display_index") if isinstance(stored, dict) else None
        if isinstance(index, int) and not isinstance(index, bool):
            left_out_indexes.add(index)
    stored_indexes = {citation.display_index for citation in citations} | left_out_indexes
    markers = {int(number) for number in _ANSWER_MARKER.findall(answer_markdown)}
    return citations, left_out + len(markers - stored_indexes)


@server.tool(
    description=(
        "Reopen the answer one of your past searches gave, by the trace_id "
        "list_past_searches returned, without running the search again. Only "
        "searches listed with has_saved_answer true can be reopened."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
async def reopen_past_answer(
    ctx: Context,
    trace_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="The trace_id of one of your past searches, from list_past_searches.",
        ),
    ],
) -> ReopenedAnswerOutput:
    """`GET /v1/history/{trace_id}/answer` over MCP: `get_saved_answer`
    with the caller's own `owner_id`.

    ONE REFUSAL FOR THREE CAUSES, exactly as REST's one 404: the row not
    existing, the row being another account's, and the row holding no saved
    answer all raise the same message, because any answer that told them
    apart would confirm to a stranger that a trace id exists and is
    someone's. `get_saved_answer` collapses the three to `None` in SQL, so
    this handler has one branch and cannot grow a second that leaks the
    difference.
    """
    user = await _authenticate_mcp_caller(ctx)
    _reject_unknown_arguments(ctx, _REOPEN_PAST_ANSWER_ARGUMENT_NAMES)

    try:
        saved = await asyncio.to_thread(
            get_saved_answer, owner_id=_owner_id_for(user), trace_id=trace_id
        )
    except ValueError:
        # `get_saved_answer` refuses an empty or over-long trace id rather
        # than querying; no caller can have a saved answer under one, so it
        # is the same "nothing saved here" as a miss, as on REST.
        saved = None
    if saved is None:
        raise MCPError(code=INVALID_PARAMS, message=_NO_SAVED_ANSWER_MESSAGE)

    citations, citations_omitted = _reopened_citations(saved.citations, saved.answer_markdown)
    audience_depth: AudienceDepth = (
        saved.depth if saved.depth in _STORED_DEPTHS else _DEFAULT_AUDIENCE_DEPTH  # type: ignore[assignment]
    )
    return ReopenedAnswerOutput(
        trace_id=saved.trace_id,
        question=saved.question,
        asked_at=saved.asked_at,
        audience_depth=audience_depth,
        answer_markdown=saved.answer_markdown,
        citations=citations,
        citations_omitted=citations_omitted,
        trust_signal=saved.trust_signal,
        trust_line=saved.trust_line,
    )


@server.tool(
    description=(
        "Tell the team what you thought of one answer: a thumbs up or down, a "
        "comment, a reason it was wrong, or the citations that do not support "
        "their claim. Send at least one of them. run_id is the one "
        "ask_biomedical_question returned. Sending feedback again for the same "
        "answer replaces the earlier one."
    ),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True),
)
async def send_answer_feedback(
    ctx: Context,
    run_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="The run_id ask_biomedical_question returned for the answer you are rating.",
        ),
    ],
    rating: Annotated[
        Literal["up", "down"] | None,
        Field(description="'up' if the answer helped, 'down' if it did not."),
    ] = None,
    comment: Annotated[
        str | None,
        Field(max_length=2000, description="Anything you want the team to read about this answer."),
    ] = None,
    flagged_reason: Annotated[
        str | None,
        Field(max_length=200, description="A short reason the answer is wrong or unsafe, if it is."),
    ] = None,
    citation_flags: Annotated[
        list[FeedbackCitationFlag] | None,
        Field(
            max_length=50,
            description="Citations that do not support their claim: each a citation_id and a reason.",
        ),
    ] = None,
) -> FeedbackRecordedOutput:
    """`POST /v1/query/{run_id}/feedback` over MCP, step for step.

    1. The run is resolved through `RunRegistry.resolve_owned_run`, the one
       ownership rule REST's `_get_owned_run` maps onto 404 and 403. Unknown
       is checked before ownership, so an evicted run reads as missing.
    2. `record_feedback` writes, and re-checks the stored row's owner under
       a row lock before any write (`feedback/writer.py`), so a refused
       caller changes nothing.
    3. The same best-effort feedback-submitted count REST fires, after a
       successful write only, with aggregates only, never the comment.

    Every field bound here is `FeedbackPayload`'s own, and `record_feedback`
    validates the payload through that model again. Retry-safe: the write
    replaces rather than appends, so a repeated call leaves one end state.
    """
    user = await _authenticate_mcp_caller(ctx)
    _reject_unknown_arguments(ctx, _SEND_ANSWER_FEEDBACK_ARGUMENT_NAMES)
    owner_id = _owner_id_for(user)

    # Refused before the run is looked up, so a call with nothing in it
    # writes nothing and learns nothing about the run (fix round,
    # F-8.10-A08). Blank text is nothing too. The REST route is unchanged.
    if (
        rating is None
        and not (comment and comment.strip())
        and not (flagged_reason and flagged_reason.strip())
        and not citation_flags
    ):
        raise MCPError(code=INVALID_PARAMS, message=_NOTHING_TO_RECORD_MESSAGE)

    try:
        entry = default_registry.resolve_owned_run(run_id, owner_id)
    except RunNotFoundError:
        raise MCPError(code=INVALID_PARAMS, message=_NO_SUCH_RUN_MESSAGE) from None
    except RunNotOwnedError:
        raise MCPError(code=INVALID_PARAMS, message=_NOT_YOUR_RUN_MESSAGE) from None

    flags = list(citation_flags or [])
    try:
        await record_feedback(
            trace_id=entry.run_id,
            owner_id=owner_id,
            rating=rating,
            comment=comment,
            flagged_reason=flagged_reason,
            citation_flags=[flag.model_dump() for flag in flags],
        )
    except InteractionNotFound:
        raise MCPError(code=INVALID_REQUEST, message=_FEEDBACK_NOT_YET_CAPTURED_MESSAGE) from None
    except FeedbackOwnershipError:
        # The same words as the registry-level refusal above, as on REST,
        # so the two refusals cannot be told apart.
        raise MCPError(code=INVALID_PARAMS, message=_NOT_YOUR_RUN_MESSAGE) from None

    feedback_properties: dict[str, bool | int | str] = {
        "has_comment": bool(comment),
        "was_flagged": bool(flagged_reason),
        "citation_flag_count": len(flags),
    }
    if rating is not None:
        feedback_properties["rating"] = rating
    await capture_event(
        AnalyticsEvent.FEEDBACK_SUBMITTED,
        distinct_id=owner_id,
        properties=feedback_properties,
    )
    return FeedbackRecordedOutput(run_id=entry.run_id, recorded=True)
