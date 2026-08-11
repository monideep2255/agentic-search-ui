"""FastAPI application entry point for the web/SSE adapter."""

import os
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sse_starlette.sse import EventSourceResponse

from system_03_search_agent.auth.dependencies import get_current_user
from system_03_search_agent.auth.router import router as auth_router
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run_registry import RunEntry, RunNotFoundError, default_registry
from system_03_search_agent.data.models import User
from system_03_search_agent.harness.cost_control import sanitize_event_for_end_user

app = FastAPI()


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
) -> EventSourceResponse:
    entry = _get_owned_run(run_id, current_user)

    async def _event_stream() -> AsyncIterator[dict[str, str]]:
        # Drains entry.queue until the None sentinel run_registry.py
        # always pushes once the run finishes (success, internal crash
        # fallback, or cancellation all funnel through the same sentinel;
        # see run_registry.py's module docstring). Each real event is
        # sanitized per-event (Section 19.4/19.5: a non-operator caller's
        # stream never carries a `cost` event or an un-redacted
        # `done.total_cost_usd`) before being forwarded as an SSE frame,
        # the event name set to the envelope's `type` and the data set to
        # the JSON payload, matching Section 12.2's client-side
        # expectation of one named event type per registered listener.
        #
        # The explicit break on `done` or a fatal `error` (rather than
        # relying only on the sentinel to end the loop) is the literal
        # acceptance criterion ("closes the stream after done or a fatal
        # error"): it closes the HTTP response at the moment the client
        # has everything it needs to stop listening, without waiting on
        # whatever the background task pushes afterward (normally just
        # the sentinel, which would arrive next regardless).
        while True:
            item = await entry.queue.get()
            if item is None:
                return
            sanitized = sanitize_event_for_end_user(item)
            if sanitized is not None:
                yield {"event": sanitized.type, "data": sanitized.model_dump_json()}
            if item.type == "done":
                return
            if item.type == "error" and item.payload.get("fatal") is True:
                return

    return EventSourceResponse(_event_stream())


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
