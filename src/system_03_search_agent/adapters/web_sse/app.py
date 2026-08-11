"""FastAPI application entry point for the web/SSE adapter."""

import logging
import os
import re
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sse_starlette.sse import EventSourceResponse

from system_03_search_agent.auth.dependencies import get_current_user
from system_03_search_agent.auth.router import router as auth_router
from system_03_search_agent.contracts.events import CitationPayload
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run_registry import RunEntry, RunNotFoundError, default_registry
from system_03_search_agent.data.models import User
from system_03_search_agent.harness.cost_control import (
    is_operator_user,
    sanitize_event_for_end_user,
)

app = FastAPI()

logger = logging.getLogger(__name__)

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
    current_user: User = Depends(get_current_user),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> CreateRunResponse:
    run_id = str(uuid.uuid4())
    query = Query(
        text=request.text,
        session_id=request.session_id,
        trace_id=run_id,
        user_id=str(current_user.id),
        audience_depth=request.audience_depth,
    )
    context = RequestContext(surface="rest_sse")
    default_registry.create_run(query, context, run_id=run_id)
    return CreateRunResponse(run_id=run_id, persona_name=_STUB_PERSONA_NAME)


def _get_owned_run(run_id: str, current_user: User) -> RunEntry:
    """Look up `run_id` and enforce ownership, raising the HTTP errors
    T-1.2-02's acceptance criteria require: 404 for an unknown run_id
    (checked first), 403 for a run that exists but belongs to a different
    authenticated caller. Shared by the events and stop endpoints below so
    the same 404-before-403 ordering and the same detail strings are never
    duplicated, and so a hardened future check applies to both call sites
    at once.
    """
    try:
        entry = default_registry.get_run(run_id)
    except RunNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such run") from None
    if entry.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="you do not own this run"
        )
    return entry


@app.get("/v1/query/{run_id}/events")
async def get_v1_query_events(
    run_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008 - idiomatic FastAPI dependency injection
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID", max_length=32),
) -> EventSourceResponse:
    # `entry` is used below only to validate `after_seq` (F-4.0-J-03).
    # `default_registry.subscribe` re-resolves `run_id` against the
    # registry on its own (T-4.0-02), which is also where resumability and
    # multi-consumer replay actually live now.
    entry = _get_owned_run(run_id, current_user)

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
    is_operator = is_operator_user(str(current_user.id))

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
    current_user: User = Depends(get_current_user),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> list[CitationPayload]:
    entry = _get_owned_run(run_id, current_user)
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
    current_user: User = Depends(get_current_user),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> StopRunResponse:
    _get_owned_run(run_id, current_user)
    # cancel_run is idempotent for a known run_id (production-standards.md
    # retry-safety gate): calling it on an already-finished or
    # already-cancelled run is a no-op, never an error, so this endpoint
    # always returns 200 once ownership is established, regardless of
    # whether the run was still in flight.
    default_registry.cancel_run(run_id)
    return StopRunResponse(stopped=True)
