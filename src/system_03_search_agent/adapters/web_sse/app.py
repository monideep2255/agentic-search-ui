"""FastAPI application entry point for the web/SSE adapter."""

from fastapi import Depends, FastAPI
from pydantic import BaseModel, ConfigDict

from system_03_search_agent.auth.dependencies import get_current_user
from system_03_search_agent.auth.router import router as auth_router
from system_03_search_agent.contracts.events import Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run
from system_03_search_agent.data.models import User
from system_03_search_agent.harness.cost_control import filter_events_for_end_user

app = FastAPI()
app.include_router(auth_router)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok")


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Query
    context: RequestContext


# Phase 1.2 builds real SSE streaming for this endpoint. This ticket (1.0)
# only proves the typed-event contract holds end to end, so it collects
# every event from run() into a list and returns one JSON array instead
# of streaming.
#
# T-2.0-08 (closes F-1.1-17): a valid Bearer access token is now required
# via `get_current_user`, which returns 401 before `run()` is ever called
# for a missing, malformed, expired, or otherwise invalid token. The
# `user_id` on the `Query` passed to `run()` is always the server-derived
# value from the verified token's subject, never the client-supplied
# `query.user_id` in the request body. `Query.user_id` stays on the wire
# contract (see contracts/query.py) so a client may still omit it; any
# value a client does send there is silently overwritten, not rejected.
#
# T-2.0-07 (Section 19.4): now that `run()` is backed by the real
# five-node graph and can actually emit a `cost` event (the phase 1.0
# scaffold never did), every end-user-facing adapter must filter it out
# before the response reaches the client. `filter_events_for_end_user`
# (harness/cost_control.py) owns that filtering logic; this is the one
# point T-2.0-03 deferred wiring it into, since no real event loop existed
# yet when that ticket was built.
@app.post("/query", response_model=list[Event])
async def post_query(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
) -> list[Event]:
    authenticated_query = request.query.model_copy(update={"user_id": str(current_user.id)})
    events = [event async for event in run(authenticated_query, request.context)]
    return filter_events_for_end_user(events)
