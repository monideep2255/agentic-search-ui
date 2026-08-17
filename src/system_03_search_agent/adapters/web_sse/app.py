"""FastAPI application entry point for the web/SSE adapter."""

import logging
import os
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from system_03_search_agent.adapters.mcp.server import server as mcp_server
from system_03_search_agent.auth.dependencies import Principal, get_caller
from system_03_search_agent.auth.router import router as auth_router
from system_03_search_agent.auth.router import source_hash_for_request
from system_03_search_agent.contracts.events import CitationPayload
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run_registry import (
    CONCURRENT_RUN_CAP_RETRY_AFTER_S,
    ConcurrentRunCapExceededError,
    RunEntry,
    RunNotFoundError,
    RunNotOwnedError,
    default_registry,
)
from system_03_search_agent.data.guest_sessions import (
    ATTEMPT_ALLOWANCE,
    FREE_RUN_ALLOWANCE,
    SpendState,
    refund_one_run,
    spend_one_anonymous_run,
)
from system_03_search_agent.data.models import (
    GuestDailyUsage,
    GuestSession,
    GuestSourceDailyUsage,
)
from system_03_search_agent.data.session import get_session, session_scope
from system_03_search_agent.harness.cost_control import (
    anon_daily_run_cap,
    anon_daily_source_share,
    is_operator_user,
    per_user_daily_query_cap,
    sanitize_event_for_end_user,
)


def _seconds_until_utc_midnight() -> int:
    """Seconds from now until the next UTC midnight, when the anonymous
    daily ceiling resets (design decision 8).

    A real number rather than a fixed constant, so a `Retry-After` a client
    honors makes it wait exactly as long as it must and no longer. Floored
    at 1: a zero would invite an immediate retry into the same refusal, and
    a negative is meaningless in the header.
    """
    now = datetime.now(UTC)
    next_midnight = datetime.combine(
        now.date() + timedelta(days=1), dt_time.min, tzinfo=UTC
    )
    return max(1, int((next_midnight - now).total_seconds()))

logger = logging.getLogger(__name__)

# Build phase 4.1 (tracker/phase_4.1.md, T-4.1-02): the outbound-only MCP
# server, mounted as a plain Starlette sub-app at `/mcp`.
#
# `streamable_http_path="/"` (rather than the SDK's own default, `/mcp`)
# is required, not cosmetic: `MCPServer.streamable_http_app()` registers
# its one route at exactly `streamable_http_path` inside the RETURNED
# sub-app, and that path is evaluated AFTER Starlette's `Mount("/mcp",
# ...)` has already stripped the `/mcp` prefix. Leaving it at the SDK
# default doubles the externally reachable path to `/mcp/mcp`. Mounting
# at `/` here means a bare `POST /mcp` 307-redirects to `/mcp/` (Starlette
# mount trailing-slash behavior), which every spec-compliant client
# already follows transparently, including the SDK's own default HTTP
# client (`create_mcp_http_client()` sets `follow_redirects=True`).
#
# `stateless_http=True`: each MCP request is independent, no session
# affinity needed, matching this adapter's own request/response (not a
# live stream) framing for `ask_biomedical_question`.
#
# Full account of both findings below: `LEARNINGS.md`'s 2026-08-11 entry
# "Mounting the mcp==2.0.0 SDK's streamable_http_app into FastAPI silently
# fails three separate ways".
_mcp_asgi_app = mcp_server.streamable_http_app(stateless_http=True, streamable_http_path="/")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Enter the mounted MCP sub-app's own Starlette lifespan.

    `MCPServer.streamable_http_app()` initializes its session manager's
    `anyio` task group inside ITS OWN `lifespan` context manager
    (`lifespan=lambda app: session_manager.run()`, set internally when the
    sub-app is built). Starlette's `Mount` does not cascade a child app's
    lifespan into the parent's automatically: nothing in FastAPI or the
    `mcp` SDK does this for you. Without entering it explicitly here,
    every request to `/mcp` fails with `RuntimeError: Task group is not
    initialized. Make sure to use run()`, in a real deployment under
    uvicorn exactly as much as under a test client, since uvicorn only
    ever sends the top-level ASGI `lifespan.startup` event to this outer
    `app`, never to a mounted sub-app on its own.
    """
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(_mcp_asgi_app.router.lifespan_context(_mcp_asgi_app))
        yield


app = FastAPI(lifespan=_lifespan)
app.mount("/mcp", _mcp_asgi_app)

# F-4.0-J-06 (judge review, build phase 4.0): matches Section 13.2's own
# `maxItems: 50` on the MCP surface's citation array. `production-
# standards.md`'s multi-agent pipeline gate requires a cap on every array;
# a run's own citation count is already implicitly bounded by Section 21's
# at-most-20-tool-calls-per-query cap, so this is defense in depth, not the
# primary bound.
_MAX_CITATIONS_PER_RUN = 50

# F-4.0-A-02/A-03 (adversary round 1, build phase 4.0): the ONLY valid
# `Last-Event-ID` shape is the digits `Event.seq` actually is (`ge=0`,
# Section 2.2), never Python's broader integer literal grammar. `int()`
# alone accepts `1_0` (underscore separators), `+3`, `-0`, hex, `inf`,
# `nan`, and a float string, every one of which is a cursor no real
# client could have produced from a wire `id:` line.
_SEQ_CURSOR_PATTERN = re.compile(r"\d+")


def _allowed_origins() -> list[str]:
    """Browser origins permitted to call this API, from CORS_ORIGINS.

    `.env` and `env.example` have declared `CORS_ORIGINS` since phase 1.0,
    but nothing read it, so the app shipped with no CORS middleware at all
    and every cross-origin browser call was blocked. The frontend runs on
    Vite's port while the API runs on its own, so that is every call the UI
    makes.

    Why no test caught it: vitest mocks `fetch`, and the Playwright suite
    drives its own base URL rather than a browser crossing two dev ports.
    Neither exercises the preflight the browser actually sends. Found by
    running the UI by hand for the first time.

    Comma separated, whitespace tolerated. Defaults to the two local dev
    ports rather than to `*`, since a wildcard with credentialed requests
    is refused by browsers anyway and is the wrong default to ship.
    """
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["http://localhost:5173", "http://localhost:3000"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    # F-4.0-J3-01 (judge round 3, build phase 4.0): `allow_headers` governs
    # what a browser may SEND, a completely separate CORS control from
    # what it may READ back off the response, which needs
    # `expose_headers`. Without it, a browser JS client cannot see
    # `GET /citations`'s `X-Run-Cancelled`/`X-Citations-Export-Truncated`
    # headers at all (F-4.0-A-05/A-13's fixes this same phase), so a
    # future frontend consumer could render a partial or truncated
    # citation export as complete with no way to know otherwise, the
    # exact trust-moat failure those two fixes exist to prevent.
    expose_headers=["X-Run-Cancelled", "X-Citations-Export-Truncated"],
)

app.include_router(auth_router)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok")


# ---------------------------------------------------------------------------
# T-1.2-02, finalized at build phase 4.0 (tracker/phase_4.0.md): the
# streaming endpoints, Technical_specification.md Section 13.1. This is now
# the one public API surface; the phase 1.0/2.0 buffered `POST /query`
# endpoint (collect every event into one JSON array, no streaming) is
# removed as of this phase. It predates the real five-node graph and the
# cost-event filtering rule (T-2.0-07), was superseded in every real caller
# by `POST /v1/query` as of build phase 1.2 (the frontend's `useAgentRun.ts`
# never called it), and Section 13.1 does not name it: keeping two parallel
# query endpoints in sync forever contradicts "finalized as the public API
# surface." Decision logged in DECISIONS.md.
# ---------------------------------------------------------------------------


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., max_length=64)
    audience_depth: Literal["clinical_brief", "researcher", "deep_technical"] = "researcher"

    @field_validator("text")
    @classmethod
    def _text_is_not_only_whitespace(cls, value: str) -> str:
        # F-1.2-05 (adversarial pass, build phase 1.2): `min_length=1` alone
        # accepts a whitespace-only string ("   "), which still passes
        # Guardrail's stub and burns a full four-call pipeline run for no
        # real query. Reject before a run is ever created, not after.
        if not value.strip():
            raise ValueError("text must not be empty or whitespace-only")
        return value


# Phase 4.5 (personalization and memory) is the ticket that assigns a real
# persona; until then every run reports this fixed placeholder rather than
# silently omitting the field (per this ticket's acceptance criteria).
_STUB_PERSONA_NAME = "Assistant"

# The one external wording for the concurrent-run cap, shared by both
# places that can refuse on it (the precheck and `create_run`'s own
# authoritative check). Named once so the two can never drift, and so
# neither is tempted to stringify the exception, whose message embeds the
# internal namespaced owner id (F-4.10-J-04; F-4.1-J3-01 is the same
# defect shape from build phase 4.1). Actionable per production-standards'
# retry-safety gate: the condition is transient and the sentence says what
# frees it.
# The one wording for "this guest token decodes, but the session behind it
# can no longer spend": migrated-and-revoked at signup, or an id with no
# row. Shared by `POST /v1/query` and `GET /v1/allowance` so the
# enforcement path and the reporting path answer identically (F-4.10-A-03).
_GUEST_SESSION_NO_LONGER_VALID_DETAIL = "this guest session is no longer valid"

# F-4.10-A-05, product-owner decision 2026-08-15. The 401 a revoked or
# unknown guest session gets is now a STRUCTURED detail rather than a bare
# string, so the client can tell it apart from every other 401 (an expired,
# tampered, or wrong-key token, all of which `get_caller` rejects with its
# own bare-string detail). The distinction is load-bearing for the browser:
# a session the server revoked at migration must NOT cause the client to
# quietly mint a fresh guest identity and hand out five more searches, while
# an ordinary 7-day token expiry legitimately should. Without a
# machine-readable reason the client cannot separate the two, and the
# adversary measured that collapsing them is a second, independent path to a
# free allowance. Additive per Section 2.6: the human-readable sentence is
# unchanged and still travels, now under `message`.
_GUEST_SESSION_REVOKED_REASON = "guest_session_revoked"

_CONCURRENT_RUN_CAP_MESSAGE = (
    "you already have the maximum number of runs in flight; "
    "wait for an existing run to finish, or stop one via "
    "POST /v1/query/{run_id}/stop, then retry"
)

# T-4.3-05, build phase 4.3: keyed by `ConcurrentRunCapExceededError.bound`
# rather than a single hardcoded message, so the catch site below branches
# on the STRUCTURAL attribute the exception now carries (never on parsing
# its `str(exc)`, which F-4.10-J-04 already forbids for this exact
# exception) instead of assuming its type can only ever mean one thing.
# `ConcurrentRunCapExceededError` represents exactly one bound today (the
# concurrency cap; the guest allowance is a wholly separate mechanism in
# `data.guest_sessions` that never raises this class), so this table has
# one entry, and `.get(...)` falls back to the same concurrency message
# for any `bound` value this table does not yet name, which keeps this
# catch site correct rather than silently blank if a future bound is
# added here before this table is updated for it.
_CONCURRENT_RUN_CAP_MESSAGES_BY_BOUND: dict[str, str] = {
    "concurrency": _CONCURRENT_RUN_CAP_MESSAGE,
}


class CreateRunResponse(BaseModel):
    run_id: str
    persona_name: str


# T-4.10-04 (design decision 6's wire shape): {kind, used, total, counted}.
# `counted` is the honesty field (design decision 6): True for a guest,
# whose count is real (guest_sessions.runs_used), False for a registered
# caller, whose count reads a structural zero because nothing writes
# `interactions` rows yet (F-2.0-04). Rendering an uncounted zero as a
# count would be the same dishonesty class as the client-side counter this
# phase removes (F-4.9-A-16).
class AllowanceResponse(BaseModel):
    kind: Literal["guest", "user"]
    used: int
    total: int
    counted: bool
    # Design decision 8, constraint 4. `used` and `total` stay this guest's
    # own true numbers; this field says whether a search is actually
    # available RIGHT NOW, which is a different question once a
    # system-wide ceiling exists above the personal one.
    #
    # Reporting "2 of 5 used" while the next request returns 429 is exactly
    # the shape F-4.10-A-03 was filed for, one level up: the reporting path
    # and the enforcement path must agree about what is available. Solving
    # it by inflating `used` to `total` was rejected, because that would
    # make the personal count itself a lie, and the personal count is what
    # migrates with the caller at signup.
    #
    # None means nothing is blocking. Additive and optional, so every
    # payload built before this existed still validates (Section 2.6).
    #
    # `guest_attempt_limit_reached` (F-4.10-R-01) is a second, additive enum
    # value for the same reason the first one exists: the attempt ceiling is
    # a bound the next request enforces, so a reporting path that could not
    # name it would promise a search that request refuses. A new enum value
    # is additive within v1 per Section 2.6.
    #
    # `anon_source_daily_cap_reached` (F-4.10-V-01) is the third, and it is
    # here for the same reason and by the same rule. It is kept distinct from
    # `anon_daily_cap_reached` because the two say different true things: one
    # means the whole anonymous product is spent for everyone today, the
    # other means THIS network has taken its share and everyone else is
    # unaffected. Rendering the first sentence for the second state would be
    # a confident wrong answer in the UI.
    blocked_reason: (
        Literal[
            "anon_daily_cap_reached",
            "anon_source_daily_cap_reached",
            "guest_attempt_limit_reached",
        ]
        | None
    ) = None


def _guest_uuid_from_owner_id(owner_id: str) -> uuid.UUID:
    """Extract the `guest_sessions.id` UUID out of a `"guest:<uuid>"`
    owner_id.

    There is NO error handling here, and this docstring used to claim
    otherwise (F-4.10-J-06, judge round 1: "the ValueError path exists as
    a defensive backstop, never expected to fire in practice"). No such
    path exists; the line below is a bare `uuid.UUID(...)`. A comment
    asserting a safety property the code does not implement is the exact
    thing this repository has been bitten by, so the claim is removed
    rather than softened.

    What is actually true. `Principal.owner_id` is only ever constructed
    by `auth.dependencies.resolve_caller_from_bearer_token` out of a
    `decode_guest_token`-verified `guest_id` claim, and `decode_guest_
    token` deliberately accepts any non-empty string there (its own
    docstring: "this function does not itself validate UUID shape"). So
    the UUID invariant is enforced only by the minter, which is the only
    holder of the derived signing key. A guest token carrying a non-UUID
    `guest_id` would therefore raise `ValueError` out of this function and
    surface as an unhandled 500, not as a handled rejection. That is
    unreachable without the signing key, which is why it is carried as
    open finding F-4.10-A-09 rather than fixed here: the fix is a decision
    about WHERE the shape belongs (the decoder's contract, or this
    reader's), not a line to add under cover of a comment correction.
    """
    return uuid.UUID(owner_id.split(":", 1)[1])


# Rate-limit consideration (T-4.10-04 acceptance criterion, the other
# half of the note on POST /auth/guest above): this is a read, and unlike
# minting, it requires get_caller to have already admitted a real
# principal (guest or registered), so an anonymous, credential-free
# caller cannot hit it at all. One SELECT at most (guest.branch), no
# model call. The same build-phase-6.0-owns-real-throttling deferral
# applies; documented here rather than left unconsidered.
@app.get("/v1/allowance", response_model=AllowanceResponse)
def get_v1_allowance(
    request: Request,
    caller: Principal = Depends(get_caller),  # noqa: B008 - idiomatic FastAPI dependency injection
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> AllowanceResponse:
    if caller.kind == "guest":
        guest_uuid = _guest_uuid_from_owner_id(caller.owner_id)
        row = session.execute(
            select(
                GuestSession.revoked_at,
                GuestSession.runs_used,
                GuestSession.attempts_used,
            ).where(GuestSession.id == guest_uuid)
        ).first()
        # F-4.10-A-03 / F-4.10-J-07 (adversary and judge round 1). This
        # branch used to select `runs_used` ALONE and report any result,
        # including no row at all, as `{used: N, total: 5, counted: true}`.
        # Two reachable shapes were measured, and both told the caller
        # they had searches left that the very next request refused with a
        # 401: a guest whose session was migrated and revoked at signup
        # (reported `used: 2` of 5), and a guest id with no row at all
        # (reported a full five available).
        #
        # `counted` is design decision 6's honesty field: it means this
        # number is a real, server-side measurement. For a session that
        # can no longer spend, no number is. The reporting path and the
        # enforcement path must agree on what a live session is, so this
        # applies the SAME predicate `spend_one_run` gates on
        # (`revoked_at IS NULL`, and a row that exists at all) and returns
        # the SAME 401 and the same detail string `POST /v1/query` returns
        # for `REVOKED_OR_UNKNOWN`. A caller now gets one consistent
        # answer from both routes instead of a promise from one and a
        # refusal from the other. This matters more than it looks: the
        # five dots in the UI render this number.
        if row is None or row[0] is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "reason": _GUEST_SESSION_REVOKED_REASON,
                    "message": _GUEST_SESSION_NO_LONGER_VALID_DETAIL,
                },
            )
        # Design decision 8, constraint 4. The daily ceiling is read here
        # for the same reason `revoked_at` is read above: whatever would
        # refuse the next request has to be visible to the path that
        # reports what is available, or the five dots promise a search that
        # does not exist. Read-only, so it never consumes the allowance it
        # is reporting on.
        #
        # ONE clock read for both shared lookups below, for the same reason
        # the spend takes one (F-4.10-V-04): two reads either side of a UTC
        # midnight would report the day's ceiling from one day and this
        # source's share from the next.
        today = datetime.now(UTC).date()
        daily_used = session.execute(
            select(GuestDailyUsage.runs_used).where(GuestDailyUsage.day == today)
        ).scalar_one_or_none()
        # F-4.10-V-01, the same constraint-4 argument applied to the bound
        # that actually stops the measured attack. A visitor behind an
        # address that has spent its share of the day is refused 429 by the
        # very next query, so a reporting path that could not name it would
        # promise a search that request refuses. Read-only, and the source is
        # resolved through the SAME function the enforcement path uses, never
        # a second notion of what a source is.
        daily_cap = anon_daily_run_cap()
        source_hash = source_hash_for_request(request)
        source_used = (
            session.execute(
                select(GuestSourceDailyUsage.runs_used).where(
                    GuestSourceDailyUsage.day == today,
                    GuestSourceDailyUsage.source_hash == source_hash,
                )
            ).scalar_one_or_none()
            if source_hash is not None
            else None
        )
        blocked: (
            Literal[
                "anon_daily_cap_reached",
                "anon_source_daily_cap_reached",
                "guest_attempt_limit_reached",
            ]
            | None
        )
        if daily_used is not None and int(daily_used) >= daily_cap:
            blocked = "anon_daily_cap_reached"
        elif source_used is not None and int(source_used) >= anon_daily_source_share(daily_cap):
            # Ranked immediately BELOW the system-wide ceiling, which is the
            # order `spend_one_anonymous_run` enforces in: it consults the
            # day first and the source second, because "the whole product is
            # spent today" is the more informative refusal and telling a
            # caller their network is full while the system is at its global
            # limit would send them to a network change that fixes nothing.
            #
            # What this ordering does NOT claim, so the next reader does not
            # have to re-derive it: the daily-versus-ATTEMPT ranking below is
            # already inverted relative to the enforcement path, which
            # evaluates both per-guest ceilings inside `_apply_spend` before
            # either shared counter is touched. A guest at its attempt
            # ceiling on a full day is refused 403
            # `guest_attempt_limit_reached` while this endpoint reports
            # `anon_daily_cap_reached`. That predates F-4.10-V-01 and is left
            # as it stands rather than silently changed under an unrelated
            # fix; both values are true of that caller, and both send them to
            # the same sign-in wall.
            blocked = "anon_source_daily_cap_reached"
        elif int(row[2]) >= ATTEMPT_ALLOWANCE and int(row[1]) < FREE_RUN_ALLOWANCE:
            # F-4.10-R-01, and the same constraint-4 argument one bound
            # further out: this guest has started as many runs as a guest may
            # start, so the next request is refused 403 no matter what the
            # dots say. The `runs_used < FREE_RUN_ALLOWANCE` half mirrors the
            # refusal ordering in `data.guest_sessions._apply_spend`, which
            # reports a spent ANSWER allowance first because that is the more
            # informative refusal; reporting the two in a different order
            # here than the enforcement path uses is how the two paths start
            # disagreeing again.
            blocked = "guest_attempt_limit_reached"
        else:
            blocked = None
        return AllowanceResponse(
            kind="guest",
            used=int(row[1]),
            total=FREE_RUN_ALLOWANCE,
            counted=True,
            blocked_reason=blocked,
        )
    # T-4.10-04's other acceptance criterion: `total` reads the SAME
    # function the enforcement path reads (harness.cost_control.
    # per_user_daily_query_cap), never a second hardcoded copy of 100.
    # `used` is a structural zero, not a measured one (F-2.0-04: nothing
    # writes `interactions` rows yet), so `counted=False` says so rather
    # than presenting an uncounted zero as a real count (F-4.9-A-16).
    return AllowanceResponse(kind="user", used=0, total=per_user_daily_query_cap(), counted=False)


def _guest_refund_callback(
    guest_uuid: uuid.UUID, spend_day: date, source_hash: str | None
) -> Callable[[bool], None]:
    """Build the refund the run registry fires when a run ends having been
    refused at the guardrail (F-4.10-A-04, F-4.10-R-01). See `post_v1_query`
    for the policy argument.

    A module-level factory rather than a closure written inline in the
    handler, so the thing under test is a named function with two inputs, and
    so the handler reads as policy rather than as plumbing.

    `charged` is supplied by the registry and says whether the refusal came
    after a real model call. It arrives through the registry's own internal
    observation of a `cost` event, never through anything the guest receives:
    see `core/run_registry.py`'s `_fire_guard_refusal_callback` for why.

    `spend_day` is the UTC day this run was CHARGED to. It now comes from
    `SpendResult.charged_day`, the day the spend statement itself used
    (F-4.10-V-04). It used to be a second `datetime.now(UTC).date()` call
    made in the handler AFTER the spend had already committed against its
    own clock read, so across a UTC midnight falling between the two the
    charge landed on day D and the refund was aimed at D+1: D stayed
    permanently over-charged and D+1 was decremented for a run it never
    took. That is exactly the defect this parameter's own docstring said had
    been designed out, which is why it is named here rather than quietly
    corrected.

    `source_hash` is the same source the spend charged (F-4.10-V-01), so a
    refunded day gives back that source's share of it too. The two move in
    lockstep, never separately: see `refund_one_run`.
    """

    def _refund(charged: bool) -> None:
        # A session of its own: the request-scoped session is closed long
        # before the agent loop reaches the guardrail. This is a blocking
        # psycopg2 call on the event loop thread, the same shape as
        # `spend_one_anonymous_run` in the handler, and bounded by the same
        # measurement (an adversary probe held a row lock for 4.0s while a
        # concurrent `GET /health` still answered in 0.005s). Behaviour
        # under real load is build phase 6.0's.
        with session_scope() as refund_session:
            refund_one_run(
                refund_session,
                guest_uuid,
                daily_day=None if charged else spend_day,
                source_hash=None if charged else source_hash,
            )

    return _refund


# run_id/trace_id wiring (per this ticket's instructions, made and
# documented rather than asked about): `RunRegistry.create_run` originally
# always minted its own `run_id` and had no way to accept one chosen
# upstream, which would have left the returned `run_id` and the `trace_id`
# threaded through every event this run produces as two independently
# minted values, breaking trace_id's "single join key" role
# (production-standards.md). The endpoint below mints one `uuid.uuid4()`
# itself, builds `Query.trace_id` from it, and passes the same value to
# `create_run(..., run_id=...)` (a small, justified addition to
# run_registry.py; see that function's own docstring), so the run_id
# returned to the caller and the trace_id on every event are always
# byte-identical, never a mismatch.
@app.post("/v1/query", response_model=CreateRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def post_v1_query(
    request: CreateRunRequest,
    http_request: Request,
    caller: Principal = Depends(get_caller),  # noqa: B008 - idiomatic FastAPI dependency injection
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> CreateRunResponse:
    # Ordering (T-4.10-05 x T-4.10-04, "spending at the wrong moment"):
    # the concurrent-run cap is checked FIRST, strictly before any guest
    # allowance is spent. This is deliberate, not incidental: the cap
    # check is a free, in-memory, no-DB read
    # (default_registry.count_active_runs_for_owner), while a guest's
    # allowance is a scarce, DB-backed resource that a refused creation
    # must never touch (this ticket's own constraint). Checking the cap
    # first means a caller already at their concurrent-run limit never
    # loses one of their five free searches to a request that was always
    # going to be refused. The reverse order (spend, then discover the cap
    # is exceeded) would require "giving back" an already-spent run, which
    # `data.guest_sessions.spend_one_run`'s API deliberately does not
    # offer (a decrement would reopen the exact read-then-write race its
    # atomic UPDATE exists to avoid), so that ordering is not just worse,
    # it is not implementable without weakening the allowance's own
    # atomicity guarantee.
    #
    # `RunRegistry.create_run` below ALSO enforces this same cap
    # internally as the actual authority (it is what `owner_id` can never
    # bypass, per T-4.10-05's acceptance criterion that `create_run`
    # itself refuses); the precheck here is a cost optimization layered on
    # top of that authority, not a replacement for it.
    #
    # F-4.10-J-10 (judge round 1) CORRECTS what this comment used to say
    # next. It described "a narrow, accepted gap": two concurrent requests
    # from the same caller interleaving between this precheck and the
    # spend below. Within one process that race is NOT reachable. This
    # handler is `async def` and contains no `await` anywhere between the
    # precheck and `create_run` (`spend_one_run` is synchronous psycopg2),
    # so two coroutines on one event loop execute the whole region
    # strictly serially and cannot interleave in it. Documenting an
    # accepted race that cannot occur is not free: it is a standing
    # instruction to a future reader not to look, and the same fact (no
    # await, therefore no interleaving) is half of why the premise gate's
    # concurrency clause was hollow until F-4.10-J-02 was fixed.
    #
    # What the authoritative check inside `create_run` is genuinely for,
    # then: a multi-process or multi-worker deployment, where two workers
    # do have separate registries and separate loops (this module's stated
    # non-coverage), and any future call path that reaches `create_run`
    # without running this precheck first, which the MCP surface already
    # does. The guest allowance's own atomicity is a separate control
    # entirely, exact at the database layer via `spend_one_run`'s
    # conditional UPDATE, and unaffected by any of this.
    #
    # One real property worth naming rather than assuming: `spend_one_run`
    # is a blocking psycopg2 call inside an `async def` handler. An
    # adversary probe held a row lock on a guest's own row for 4.0s and
    # measured a concurrent `GET /health` still answering in 0.005s, so it
    # does not stall the whole loop in practice today; behaviour under
    # real load is build phase 6.0's, not an assumption to rest on here.
    if default_registry.count_active_runs_for_owner(caller.owner_id) >= (
        default_registry.max_active_runs_per_owner
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "reason": "concurrent_run_cap_exceeded",
                "message": _CONCURRENT_RUN_CAP_MESSAGE,
            },
            headers={"Retry-After": str(CONCURRENT_RUN_CAP_RETRY_AFTER_S)},
        )

    # The refund needs the day the spend actually charged and the source it
    # charged (F-4.10-V-04, F-4.10-V-01), so both are bound here and read
    # after the spend rather than recomputed later.
    guest_spend_day: date | None = None
    guest_source_hash: str | None = None

    if caller.kind == "guest":
        guest_uuid = _guest_uuid_from_owner_id(caller.owner_id)
        # design decision 8 plus F-4.10-V-01: ALL FOUR bounds, in one call,
        # because each of the first three is keyed on something that does not
        # bound one caller. The per-guest ceilings are keyed on a guest
        # identity, and `POST /auth/guest` mints identities for free (the
        # adversary round accepted 40 paid pipelines in 0.25 seconds by
        # minting one guest per run, F-4.10-A-01). The daily ceiling is keyed
        # on the calendar day, so it holds the system's money and says
        # nothing about who spent it: 20 identities from ONE source took all
        # 200 of the day's runs in 1.84 seconds with the mint throttle live
        # and refusing nothing. The source share is the bound that stops
        # that, and it stops it however many identities the caller mints.
        #
        # Every one of the three is keyword-only with no default precisely so
        # this call site cannot quietly lose a bound in a later refactor.
        guest_source_hash = source_hash_for_request(http_request)
        daily_cap = anon_daily_run_cap()
        spend = spend_one_anonymous_run(
            session,
            guest_uuid,
            daily_cap=daily_cap,
            source_hash=guest_source_hash,
            source_cap=anon_daily_source_share(daily_cap),
        )
        guest_spend_day = spend.charged_day
        if spend.state is SpendState.SOURCE_DAILY_CAP_REACHED:
            # F-4.10-V-01. A 429 like the system-wide ceiling above, and for
            # the same reason: this bound is genuinely transient, resets at
            # the same UTC midnight, and signing in bypasses it entirely, so
            # `Retry-After` is the real number of seconds to that reset.
            #
            # A DISTINCT reason and a DISTINCT sentence, because collapsing
            # it into `anon_daily_cap_reached` would tell this caller the
            # whole product is spent for everyone when it is not, and would
            # hide from an operator reading refusal reasons the difference
            # between "we are popular today" and "one address is hammering
            # us". The message says what is actually true and what actually
            # helps: signing in works right now, and it is this network's
            # share rather than the system that is spent.
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "reason": "anon_source_daily_cap_reached",
                    "message": (
                        "guest searches from this network have reached their "
                        "share of today's limit; signing in or creating an "
                        "account works immediately, or try again tomorrow"
                    ),
                },
                headers={"Retry-After": str(_seconds_until_utc_midnight())},
            )
        if spend.state is SpendState.DAILY_CAP_REACHED:
            # 429, not the 403 an exhausted personal allowance gets, and the
            # difference is not cosmetic. This ceiling is genuinely
            # transient: it resets at UTC midnight, and signing in bypasses
            # it entirely right now. Retry-After is the real number of
            # seconds to that reset, not a guess, so a client that honors it
            # waits exactly as long as it needs to.
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "reason": "anon_daily_cap_reached",
                    "message": (
                        "anonymous searches are at their daily limit for "
                        "everyone right now; signing in or creating an "
                        "account works immediately, or try again tomorrow"
                    ),
                },
                headers={"Retry-After": str(_seconds_until_utc_midnight())},
            )
        if spend.state is SpendState.EXHAUSTED:
            # design decision 5: 403, never 429. The allowance is SPENT,
            # not rate limited: retrying later does not help, so a 429
            # with a Retry-After would be a lie the UI would repeat to the
            # user. `guest_allowance_exhausted` is the machine-readable
            # reason the UI branches the sign-in wall on.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "reason": "guest_allowance_exhausted",
                    "message": (
                        "you have used all of your free searches; sign in or "
                        "create an account to keep going"
                    ),
                },
            )
        if spend.state is SpendState.ATTEMPTS_EXHAUSTED:
            # F-4.10-R-01. 403 like the exhausted personal allowance above,
            # and for design decision 5's reason: this ceiling is permanent
            # for this identity, so a 429 with a Retry-After would be a lie
            # the UI would repeat as "try again soon". A DISTINCT
            # machine-readable reason, because the two mean different things
            # to the person reading them and the sign-in wall has to say
            # something true for each: "you have used your free searches" is
            # false for a caller who never got an answer at all.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "reason": "guest_attempt_limit_reached",
                    "message": (
                        "you have asked as many questions as a guest can; "
                        "sign in or create an account to keep going"
                    ),
                },
            )
        if spend.state is SpendState.REVOKED_OR_UNKNOWN:
            # This guest session was migrated (and revoked) at signup/
            # login, or never existed. The token still decodes, so
            # get_caller admitted it, but it is no longer a spendable
            # identity: a 401 matches "this credential is no longer
            # valid" more than a 403 ("you are you, but not permitted"),
            # and the premise gate accepts either for this exact case.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "reason": _GUEST_SESSION_REVOKED_REASON,
                    "message": _GUEST_SESSION_NO_LONGER_VALID_DETAIL,
                },
            )

    # F-4.10-A-04, product-owner decision 2026-08-15: a guardrail refusal
    # must not cost a guest one of their five free searches. A first-time
    # visitor who asks five off-topic questions would otherwise meet the
    # sign-in wall having never received a single answer, and the guardrail
    # catches far more than injections: off-topic, malformed, and
    # out-of-scope questions all land here.
    #
    # THIS IS A REFUND, NOT A DEFERRED CHARGE, and the distinction is the
    # whole design. The spend happens above, when the run is CREATED, because
    # that is the only point at which admission can be bounded; the guardrail
    # refuses LATER, inside the agent loop, long after this handler has
    # returned 202. Moving the spend to after the guardrail was rejected: it
    # would let a caller start unbounded runs that never spend at all, which
    # is a strictly worse hole than the one being closed. So the compensation
    # runs when the refusal becomes observable, in the registry's own drain
    # loop (`core/run_registry.py`'s `_fire_guard_refusal_callback`).
    #
    # WHAT IT REFUNDS, and what it deliberately does not. F-4.10-R-01,
    # product-owner decision 2026-08-15, corrects what this comment used to
    # say, and the correction matters because building on the old text is
    # what produced the critical.
    #
    # It used to claim a refused run "still paid for a real Guard-tier model
    # call". That is FALSE for the cheapest refusal available:
    # `core/graph.py:753` returns `_decline_for_guardrail(..., charged=False)`
    # for a pre-filter verdict, before any model call at all. Combined with
    # refunding the personal allowance, that removed the only per-identity
    # bound: a caller sending nothing but refusable text never advanced
    # `runs_used`, so the only counter that moved was the SHARED daily one.
    # Measured: one guest token, minted once, started 200 paid pipelines in
    # 1.68 seconds with its own allowance still reading `used: 0`, exhausted
    # the whole day's anonymous budget, and a brand-new visitor asking a
    # legitimate question was then refused 429.
    #
    # THREE COUNTERS NOW, and each answers a different question:
    #
    # - The ATTEMPT (`guest_sessions.attempts_used`) is never refunded. It is
    #   the per-identity bound, and it is what makes the refund below safe.
    # - The ANSWER (`guest_sessions.runs_used`) is always refunded on a
    #   guardrail refusal. A visitor must not be pushed toward the sign-in
    #   wall by questions that were never answered, and the guardrail catches
    #   far more than injections: off-topic, malformed and out-of-scope
    #   questions all land there.
    # - The DAY (`guest_daily_usage.runs_used`) is refunded only when the
    #   refusal made NO model call. That budget bounds SPEND, so charging it
    #   for a refusal that spent nothing is what made the drain cheap; but a
    #   refusal that came after a real Guard-tier call did spend money, and
    #   refunding it there would be the free-compute path the original
    #   decision was right to avoid.
    #
    # The callback learns which case it is from its `charged` argument, which
    # the registry observes internally and which no guest ever sees. That is
    # deliberate: Sections 19.4 and 19.5 make cost internal-only, and this
    # phase's premise gate asserts a guest is never streamed a `cost` event,
    # so a `charged` flag on `GuardPayload` would tell every guest which of
    # their questions cost money.
    #
    # IF THE PROCESS DIES between the refusal and the refund, the refund is
    # lost and the guest stays charged for a run that produced nothing. That
    # is the safe direction of the two: the alternative failure, a refund
    # that lands without the refusal having happened, would hand out free
    # searches. Closing the residue properly needs the durable run record
    # build phase 4.6 owns; there is nothing to reconcile against today.
    on_guard_refused: Callable[[bool], None] | None = (
        _guest_refund_callback(
            _guest_uuid_from_owner_id(caller.owner_id),
            guest_spend_day,
            guest_source_hash,
        )
        # `guest_spend_day is not None` rather than `caller.kind == "guest"`,
        # and the difference is F-4.10-V-04's fix rather than a style choice:
        # the day the refund targets must be the day the SPEND charged, so
        # the callback is built from the spend's own report and cannot exist
        # without one. Every guest that reaches this line spent successfully
        # (every other outcome raised above), so this is not a silent skip.
        if guest_spend_day is not None
        else None
    )

    run_id = str(uuid.uuid4())
    query = Query(
        text=request.text,
        session_id=request.session_id,
        trace_id=run_id,
        user_id=caller.user_id,
        audience_depth=request.audience_depth,
    )
    context = RequestContext(surface="rest_sse")
    try:
        default_registry.create_run(
            query,
            context,
            run_id=run_id,
            owner_id=caller.owner_id,
            on_guard_refused=on_guard_refused,
        )
    except ConcurrentRunCapExceededError as exc:
        # The authoritative check inside create_run refused what the
        # precheck above admitted. Still a 429, and now BYTE-IDENTICAL in
        # shape and wording to the precheck's own rejection above: one
        # condition should not produce two different external messages
        # depending on which of the two layers happened to catch it.
        #
        # F-4.10-J-04: this used to be `str(exc)`, and
        # `ConcurrentRunCapExceededError`'s own string embeds the internal
        # namespaced owner id (`user:<uuid>` / `guest:<uuid>`).
        # `tracker/BOARD.md` records F-4.1-J3-01 against exactly that
        # habit, raw exception stringification into an external-facing
        # message. Nothing derived from the exception reaches the caller
        # now except its `retry_after_s`, which is a number the caller
        # needs and which discloses nothing.
        #
        # T-4.3-05: the message is now looked up by `exc.bound`, the
        # structural attribute the exception carries (never re-derived
        # from `str(exc)`, for the same F-4.10-J-04 reason above), so this
        # site actually branches on which bound was hit rather than
        # assuming every `ConcurrentRunCapExceededError` means the same
        # thing forever. The `reason` string on the wire is left
        # unchanged: `concurrent_run_cap_exceeded` is already asserted by
        # the frontend and the CLI client (frontend/src/lib/api.ts,
        # tests/.../adapters/cli/test_client.py), and it was already
        # unambiguous, since the guest-allowance refusal is a completely
        # separate code path with its own `guest_allowance_exhausted`
        # reason (this same function's `SpendState.EXHAUSTED` branch,
        # above). What was ambiguous was only the NUMBER the two caps
        # happened to share, which T-4.3-05 fixed at the source (`core/
        # run_registry.py`'s `DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER`), not by
        # renaming a reason string every consumer already keys on.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "reason": "concurrent_run_cap_exceeded",
                "message": _CONCURRENT_RUN_CAP_MESSAGES_BY_BOUND.get(
                    exc.bound, _CONCURRENT_RUN_CAP_MESSAGE
                ),
            },
            headers={"Retry-After": str(exc.retry_after_s)},
        ) from None
    return CreateRunResponse(run_id=run_id, persona_name=_STUB_PERSONA_NAME)


def _get_owned_run(run_id: str, caller: Principal) -> RunEntry:
    """Look up `run_id` and enforce ownership, raising the HTTP errors
    T-1.2-02's acceptance criteria require: 404 for an unknown run_id
    (checked first), 403 for a run that exists but belongs to a different
    caller. Shared by the events, citations, and stop endpoints below so
    the same 404-before-403 ordering and the same detail strings are never
    duplicated, and so a hardened future check applies to every call site
    at once.

    T-4.10-03 (design decision 2): compares `entry.owner_id` and NOTHING
    else, the namespaced `user:<uuid>`/`guest:<uuid>` identity, so a
    guest can never read/stop/export another guest's or any user's run,
    and the reverse.

    T-4.3-07, build phase 4.3: the RULE itself now lives in
    `RunRegistry.resolve_owned_run`, and this function is the HTTP mapping
    of its two domain errors. Behavior here is unchanged, deliberately and
    to the letter: the same unknown-before-ownership ordering, the same two
    status codes, the same two detail strings. What changed is only that a
    second delivery surface (GraphQL) can now enforce the identical rule
    without either copying this check or importing this module, which it
    cannot do, since `app.py` imports the GraphQL router in order to mount
    it and the reverse import would be circular. An authorization rule that
    exists in two places is one that will eventually differ in one of them.
    """
    try:
        return default_registry.resolve_owned_run(run_id, caller.owner_id)
    except RunNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such run") from None
    except RunNotOwnedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="you do not own this run"
        ) from None


@app.get("/v1/query/{run_id}/events")
async def get_v1_query_events(
    run_id: str,
    caller: Principal = Depends(get_caller),  # noqa: B008 - idiomatic FastAPI dependency injection
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID", max_length=32),
) -> EventSourceResponse:
    # `entry` is used below only to validate `after_seq` (F-4.0-J-03).
    # `default_registry.subscribe` re-resolves `run_id` against the
    # registry on its own (T-4.0-02), which is also where resumability and
    # multi-consumer replay actually live now.
    entry = _get_owned_run(run_id, caller)

    # T-4.0-03 (resumability, Section 13.1): a reconnecting client sends
    # back the last `seq` it saw as `Last-Event-ID` (this backend's
    # `fetch`-based SSE client, unlike a native `EventSource`, can set an
    # arbitrary request header, so no query-param fallback is needed). A
    # genuinely ABSENT header means "new client, full replay",
    # `subscribe`'s own default, since every real `seq` is `>= 0`
    # (Section 2.2).
    #
    # F-4.0-A-02 (adversary round 1, build phase 4.0): a PRESENT but
    # malformed header used to fall back to the same full-replay default
    # as an absent one, silently producing exactly the duplicate delivery
    # the phase premise forbids ("never a gap, never a duplicate"), while
    # an out-of-range-but-well-formed cursor was correctly rejected below.
    # Both are cursors this run cannot honor; only one was an error. A
    # present header now must be the strict digit grammar `seq` actually
    # is (F-4.0-A-03) or it is rejected the same way an out-of-range one
    # is, never silently reinterpreted as "start over".
    if last_event_id is None:
        after_seq = -1
    elif _SEQ_CURSOR_PATTERN.fullmatch(last_event_id):
        after_seq = int(last_event_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Last-Event-ID {last_event_id!r} is not a valid seq cursor "
                "(expected digits only); omit the header for a fresh replay "
                "rather than sending a value this run cannot resolve"
            ),
        )

    # F-4.0-J-03 (judge review, build phase 4.0): `after_seq` is validated
    # against what this run has actually produced so far, using the same
    # `entry` the ownership check above already fetched. A genuine client's
    # `Last-Event-ID` can only ever be a `seq` this registry already
    # emitted; a value beyond that is either a malformed header or an
    # attempt to hold `subscriber_count` above zero indefinitely without
    # ever receiving an event, which would silently defeat F-1.2-02's
    # abandonment check (a run nobody can actually be served to would never
    # be recognized as unwatched). Checked here, before `EventSourceResponse`
    # is constructed, specifically so a rejection is a real `400` rather
    # than an error raised after the stream has already started with `200`.
    current_max_seq = entry.events[-1].seq if entry.events else -1
    if after_seq > current_max_seq:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Last-Event-ID {after_seq} exceeds this run's highest emitted "
                f"seq ({current_max_seq}); a client cannot resume past an event "
                "this run has not produced yet"
            ),
        )

    # T-4.0-05 (Section 19.4/19.5): visibility is derived once per request,
    # purely from the authenticated caller's `OPERATOR_USER_IDS` allowlist
    # membership, never from anything in the request body or headers. There
    # is no operator-related field on any request model to read here; that
    # absence is the point.
    #
    # F-4.0-A-08 (adversary round 1, build phase 4.0): this snapshot is
    # deliberately per-CONNECTION, not re-checked per-event. Revoking an
    # operator's allowlist membership mid-stream does not affect an
    # already-open connection; it takes effect on that caller's NEXT
    # request. This is an accepted design decision, not an oversight: the
    # allowlist check happens once, here, rather than once per event
    # inside `_event_stream` below, so a long deep-research stream is not
    # paying a live env-var read on every yielded event for a revocation
    # scenario expected to be rare. Stated explicitly because
    # `_operator_user_ids()` (harness/cost_control.py) is itself written
    # to be live-reloadable, which could otherwise read as a promise this
    # call site does not keep.
    # T-4.10-03: `caller.user_id` is None for a guest, and
    # `is_operator_user(None)` is already required to return False (see
    # that function's own docstring), so a guest is never an operator by
    # construction, never by a special case here.
    is_operator = is_operator_user(caller.user_id)

    async def _event_stream() -> AsyncIterator[dict[str, str]]:
        # `subscribe` (T-4.0-02) yields every buffered event with
        # `seq > after_seq` and then follows the live tail, on its own
        # ending the generator after a `done` or a fatal `error` (or when
        # the run finishes with neither), so no separate break condition
        # is needed here. Each event is sanitized per-event for a
        # non-operator caller (Section 19.4/19.5: never a `cost` event,
        # never an un-redacted `done.total_cost_usd`); an operator caller
        # gets every event unredacted. The event name is set to the
        # envelope's `type` and the data to the JSON payload, matching
        # Section 12.2's client-side expectation of one named event type
        # per registered listener.
        #
        # F-4.0-J-01 (judge review, build phase 4.0): `id` is the envelope's
        # own `seq`, not a per-connection counter. `sse_starlette` writes
        # this as the frame's `id:` line, which is the ONLY channel a
        # standards-conforming SSE client (a native `EventSource`, or any
        # off-the-shelf client library build phase 4.2's CLI might use) has
        # for `Last-Event-ID` on reconnect; Section 2024 of the tech spec
        # names `seq` explicitly as what `Last-Event-ID` is "keyed off".
        # Using the envelope `seq` (not a resend-loop-local counter) is
        # required for correctness across the cost-event filter above: a
        # non-operator caller never sees `seq` 1, 3, 5, ... (cost events),
        # so a per-connection counter would renumber the visible events
        # and desync from what `subscribe(after_seq=...)` expects on the
        # next reconnect, while the real envelope `seq` resumes correctly
        # through that same gap.
        #
        # F-4.0-A-09 (adversary round 1, build phase 4.0): named tradeoff,
        # not an oversight. The gaps in a non-operator's visible `id:`
        # sequence (0, 2, 4, ... never 1, 3, 5) disclose exactly how many
        # `cost` events were filtered and roughly where in the pipeline
        # each occurred, which is itself cost-adjacent metadata
        # (harness/cost_control.py's own comment: "cost and token usage
        # are internal-only data"). The alternative, a per-connection
        # counter with no gaps, was rejected above for a real correctness
        # reason (F-4.0-J-01), so this is the accepted cost of that
        # choice, not a separate defect to fix independently.
        async for item in default_registry.subscribe(run_id, after_seq=after_seq):
            forwarded = item if is_operator else sanitize_event_for_end_user(item)
            if forwarded is not None:
                yield {
                    "id": str(forwarded.seq),
                    "event": forwarded.type,
                    "data": forwarded.model_dump_json(),
                }

    return EventSourceResponse(_event_stream())


# T-4.0-04: the citations export endpoint. Reuses `_get_owned_run` for the
# same 404 (unknown run_id) / 403 (wrong owner) ordering the events and
# stop endpoints already enforce. No operator-mode consideration applies
# here: `CitationPayload` carries no cost data, so there is nothing to
# redact for either caller class.
@app.get(
    "/v1/query/{run_id}/citations",
    response_model=Annotated[list[CitationPayload], Field(max_length=_MAX_CITATIONS_PER_RUN)],
)
async def get_v1_query_citations(
    run_id: str,
    response: Response,
    caller: Principal = Depends(get_caller),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> list[CitationPayload]:
    entry = _get_owned_run(run_id, caller)
    if not entry.finished:
        # production-standards.md's retry-safety gate: the error says what
        # to do next, not just what failed. `run_streaming()` never raises
        # (its own docstring), so `entry.finished` becoming True is the
        # only reliable terminal signal; there is no separate "failed"
        # state to special-case here.
        #
        # F-4.0-A-06 (adversary round 1, build phase 4.0): the message used
        # to name "the done event" specifically, but a run that gets
        # stopped or abandonment-cancels never emits one (see F-4.0-A-04's
        # fix: a cancelled run's terminal event is a fatal `error`, not
        # `done`). Reworded to name the real, complete set of ways a run
        # ends, not just the normal-completion path.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "run has not reached a terminal state yet; poll GET "
                "/v1/query/{run_id}/events or retry this request once the "
                "stream ends (a done event, or a stop or cancellation)"
            ),
        )
    # A run that ended via a fatal error with no citations correctly
    # returns an empty list here, not an error: reaching a terminal state
    # is what this endpoint gates on, not reaching the `done` event
    # specifically.
    #
    # F-4.0-A-05 (adversary round 1, build phase 4.0): a run stopped or
    # abandonment-cancelled partway through reaches this same terminal
    # state (`entry.finished`) as a genuinely complete run, so its
    # citation list, real but partial, was indistinguishable from a
    # complete run that legitimately cited nothing. `X-Run-Cancelled`
    # discloses the distinction as response metadata rather than changing
    # the body's wire shape (still a bare JSON array, per Section 13.1),
    # which build phase 4.1's MCP surface and 4.2's CLI can read without
    # a breaking contract change.
    if entry.cancelled:
        response.headers["X-Run-Cancelled"] = "true"
    #
    # F-4.0-A-12 (adversary round 1, build phase 4.0, carried open): a
    # separate truncation disclosure exists upstream, `core/graph.py`'s
    # `citations_capped` (the `_MAX_CITATIONS_PER_ANSWER` cut, F-2.1-C12's
    # honesty guarantee), but it is currently only woven into the
    # narrative `token` text or a non-fatal refusal `error`, never onto
    # `DonePayload`, so this endpoint (which reads only `citation`-typed
    # events) has no field to read it from. The correct fix threads a new
    # additive `DonePayload` field through `core/graph.py`'s several
    # `write_node` exit branches, which deserves its own focused,
    # separately tested change rather than a rushed addition at the tail
    # of this round; tracked in tracker/phase_4.0.md's Open items.
    #
    # F-4.0-J-06 (judge review, build phase 4.0): `CitationPayload` is
    # `extra="forbid"`, so constructing it from a malformed `citation`
    # payload would otherwise raise unhandled, turning one bad record into
    # a 500 for the whole export. `core.write_node` is the only shipped
    # producer of a `citation` event today and already builds this shape
    # through `CitationPayload(...).model_dump()`, so this is not expected
    # to fire; it exists so a future producer's bug degrades to "one
    # citation missing, logged" rather than "the whole export breaks".
    citation_events_total = sum(1 for event in entry.events if event.type == "citation")
    citations: list[CitationPayload] = []
    for event in entry.events:
        if event.type != "citation":
            continue
        try:
            citations.append(CitationPayload(**event.payload))
        except (TypeError, ValueError):
            logger.warning(
                "run %s produced a citation event whose payload does not "
                "match CitationPayload; omitted from the export",
                run_id,
            )
        if len(citations) >= _MAX_CITATIONS_PER_RUN:
            break
    # F-4.0-A-13 (adversary round 1, build phase 4.0): the local
    # `_MAX_CITATIONS_PER_RUN` break above is unreachable today (verified:
    # `core/graph.py`'s own `_MAX_CITATIONS_PER_ANSWER = 20` is the only
    # producer and cuts well below 50), but was itself an undisclosed
    # silent truncation, the same shape phase 3.2's `_cap()` finding was
    # fixed for, with nothing enforcing the 2.5x margin that makes it safe
    # today. Disclosed defensively so raising the upstream cap past 50 in
    # a later phase degrades to "the header says so" rather than "a live
    # silent-truncation path with no failing test".
    if citation_events_total > _MAX_CITATIONS_PER_RUN:
        response.headers["X-Citations-Export-Truncated"] = "true"
    return citations


class StopRunResponse(BaseModel):
    stopped: bool


@app.post("/v1/query/{run_id}/stop", response_model=StopRunResponse)
async def post_v1_query_stop(
    run_id: str,
    caller: Principal = Depends(get_caller),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> StopRunResponse:
    _get_owned_run(run_id, caller)
    # cancel_run is idempotent for a known run_id (production-standards.md
    # retry-safety gate): calling it on an already-finished or
    # already-cancelled run is a no-op, never an error, so this endpoint
    # always returns 200 once ownership is established, regardless of
    # whether the run was still in flight.
    default_registry.cancel_run(run_id)
    return StopRunResponse(stopped=True)
