"""FastAPI application entry point for the web/SSE adapter."""

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from system_03_search_agent.contracts.events import Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run

app = FastAPI()


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
@app.post("/query", response_model=list[Event])
async def post_query(request: QueryRequest) -> list[Event]:
    return [event async for event in run(request.query, request.context)]
