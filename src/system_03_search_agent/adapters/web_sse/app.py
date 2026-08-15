"""FastAPI application entry point for the web/SSE adapter."""

import logging
import os
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from system_03_search_agent.adapters.mcp.server import server as mcp_server
from system_03_search_agent.auth.dependencies import Principal, get_caller
from system_03_search_agent.auth.router import router as auth_router
from system_03_search_agent.contracts.events import CitationPayload
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run_registry import (
    CONCURRENT_RUN_CAP_RETRY_AFTER_S,
    ConcurrentRunCapExceededError,
    RunEntry,
    RunNotFoundError,
    default_registry,
)
from system_03_search_agent.data.guest_sessions import FREE_RUN_ALLOWANCE, SpendState, spend_one_run
from system_03_search_agent.data.models import GuestSession
from system_03_search_agent.data.session import get_session
from system_03_search_agent.harness.cost_control import (
    is_operator_user,
    per_user_daily_query_cap,
    sanitize_event_for_end_user,
)

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


def _guest_uuid_from_owner_id(owner_id: str) -> uuid.UUID:
    """Extract the `guest_sessions.id` UUID out of a `"guest:<uuid>"`
    owner_id. `Principal.owner_id` is only ever constructed by `auth.
    dependencies.resolve_caller_from_bearer_token` out of a `decode_guest_
    token`-verified `guest_id` claim, so this is always well-formed for a
    Principal actually reaching this function; the ValueError path exists
    as a defensive backstop, never expected to fire in practice.
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
    caller: Principal = Depends(get_caller),  # noqa: B008 - idiomatic FastAPI dependency injection
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> AllowanceResponse:
    if caller.kind == "guest":
        guest_uuid = _guest_uuid_from_owner_id(caller.owner_id)
        used = session.execute(
            select(GuestSession.runs_used).where(GuestSession.id == guest_uuid)
        ).scalar_one_or_none()
        # A guest whose session row cannot be found (evicted from the DB
        # somehow, though nothing in this codebase deletes guest_sessions
        # rows today) is reported as a fresh, uncounted zero rather than a
        # 404/500: this endpoint's job is to describe the allowance
        # honestly, not to re-litigate whether the token itself is valid
        # (get_caller already gated that before this function ever runs).
        return AllowanceResponse(
            kind="guest", used=int(used) if used is not None else 0, total=FREE_RUN_ALLOWANCE, counted=True
        )
    # T-4.10-04's other acceptance criterion: `total` reads the SAME
    # function the enforcement path reads (harness.cost_control.
    # per_user_daily_query_cap), never a second hardcoded copy of 100.
    # `used` is a structural zero, not a measured one (F-2.0-04: nothing
    # writes `interactions` rows yet), so `counted=False` says so rather
    # than presenting an uncounted zero as a real count (F-4.9-A-16).
    return AllowanceResponse(kind="user", used=0, total=per_user_daily_query_cap(), counted=False)


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
    # top of that authority, not a replacement for it. A narrow, accepted
    # gap follows from layering the two: under a true race between two
    # concurrent requests from the SAME caller landing between this
    # precheck and the guest-allowance spend below, the precheck could
    # pass for both, one could spend an allowance run, and `create_run`
    # could still refuse it a moment later on the authoritative check.
    # This is consistent with this phase's own stated non-coverage
    # (multi-request races on this specific cap are out of scope; the
    # guest allowance's OWN atomicity is unaffected and remains exact via
    # its independent DB-level atomic UPDATE, which is the property the
    # premise gate's concurrency arm actually tests).
    if default_registry.count_active_runs_for_owner(caller.owner_id) >= (
        default_registry.max_active_runs_per_owner
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "reason": "concurrent_run_cap_exceeded",
                "message": (
                    "you already have the maximum number of runs in flight; "
                    "wait for an existing run to finish, or stop one via "
                    "POST /v1/query/{run_id}/stop, then retry"
                ),
            },
            headers={"Retry-After": str(CONCURRENT_RUN_CAP_RETRY_AFTER_S)},
        )

    if caller.kind == "guest":
        guest_uuid = _guest_uuid_from_owner_id(caller.owner_id)
        spend = spend_one_run(session, guest_uuid)
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
        if spend.state is SpendState.REVOKED_OR_UNKNOWN:
            # This guest session was migrated (and revoked) at signup/
            # login, or never existed. The token still decodes, so
            # get_caller admitted it, but it is no longer a spendable
            # identity: a 401 matches "this credential is no longer
            # valid" more than a 403 ("you are you, but not permitted"),
            # and the premise gate accepts either for this exact case.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="this guest session is no longer valid",
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
        default_registry.create_run(query, context, run_id=run_id, owner_id=caller.owner_id)
    except ConcurrentRunCapExceededError as exc:
        # The rare race the comment above names: the precheck passed but
        # the authoritative check inside create_run did not. Still a 429,
        # same shape as the precheck's own rejection above.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "reason": "concurrent_run_cap_exceeded",
                "message": str(exc),
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
    """
    try:
        entry = default_registry.get_run(run_id)
    except RunNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such run") from None
    if entry.owner_id != caller.owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="you do not own this run"
        )
    return entry


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
