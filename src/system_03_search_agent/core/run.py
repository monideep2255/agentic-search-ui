"""The run() entry point: Section 2.1, Technical_specification.md.

This is a typed-event scaffold only. It does not call an LLM, does not call
any tool, and does not implement the real Guardrail-Think-Plan-Act-Write
loop. It proves the typed-event mechanism end to end: one `guard` event,
then one `done` event, both schema-valid against the `Event` envelope.
"""

import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from system_03_search_agent.contracts.events import DonePayload, Event, GuardPayload
from system_03_search_agent.contracts.query import Query, RequestContext


async def run(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """The single internal interface every surface calls.

    Never returns a bare string or a raw model completion. Every unit of
    output is a typed Event from the taxonomy in Section 2.3.
    """
    start = time.monotonic()
    seq = 0

    guard_payload = GuardPayload(passed=True, category="ok", reason=None)
    yield Event(
        type="guard",
        version="v1",
        trace_id=query.trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=guard_payload.model_dump(),
    )
    seq += 1

    elapsed_ms = int((time.monotonic() - start) * 1000)
    done_payload = DonePayload(
        total_cost_usd=0.0,
        total_tool_calls=0,
        elapsed_ms=elapsed_ms,
        trust_outcome="answer",
    )
    yield Event(
        type="done",
        version="v1",
        trace_id=query.trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=done_payload.model_dump(),
    )
