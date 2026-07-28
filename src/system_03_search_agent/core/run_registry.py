"""In-process run registry: T-1.2-01, `tracker/phase_1.2.md`.

Tracks every in-flight (or recently finished) streaming run so a later
ticket's HTTP surface (T-1.2-02: `POST /v1/query`, `GET
/v1/query/{run_id}/events`, `POST /v1/query/{run_id}/stop`) can create a
run, hand a client back a `run_id` immediately, let that client (or a
different request entirely, since SSE reconnects on a fresh HTTP
connection) attach to the run's event stream, and stop a run on request.

This module owns none of that HTTP wiring. It owns exactly three things:
starting `core.run.run_streaming()` as a background task that drains into
a per-run queue, looking a run up by id, and cancelling a run by id. Per
this ticket's explicit scope, this is in-process, module-level state: a
plain dict keyed by `run_id`, with no persistence and no multi-process
coordination. A run created on one worker process is invisible to another;
that is an accepted, documented limitation of this phase, not an oversight
(the scope note in `tracker/phase_1.2.md` names this ticket's shape as
"minimal REAL version", not the finalized Section 13.1 API).

Depends on:
    - system_03_search_agent.core.run (run_streaming)
    - system_03_search_agent.contracts.events (Event)
    - system_03_search_agent.contracts.query (Query, RequestContext)

Reads:
    - Nothing directly.

Writes:
    - Nothing directly. All state lives in the `RunRegistry` instance's
      own in-process dict and the `asyncio.Queue`/`asyncio.Task` objects
      it creates.

Design decisions, made here rather than asked about, per this ticket's
instruction to make the most reasonable engineering call and document it:

    - Ownership is derived from `query.user_id`, not passed as a separate
      parameter. By the time a `Query` reaches `core.run` on the
      authenticated `rest_sse` surface, T-2.0-08 has already overwritten
      `user_id` with the caller's real, server-verified UUID, so it is
      already the authoritative owner for this query. `None` is a valid,
      tracked owner (an unauthenticated or not-yet-wired surface), not an
      error; a later ticket's ownership check decides what `None` means
      for authorization, which is out of this ticket's scope.
    - `get_run` raises the named `RunNotFoundError` for an unknown
      `run_id`, rather than returning `None`. A later ticket's endpoint
      needs to distinguish "no such run" (404) from "run exists, wrong
      owner" (403); a raised, named exception makes that branch explicit
      at the call site instead of relying on every caller to remember to
      check for `None`.
    - `cancel_run` also raises `RunNotFoundError` for a genuinely unknown
      `run_id` (the id was never created, e.g. a garbage `run_id` in a
      client request), but is a no-op, never raising, for a `run_id` that
      exists but whose background task has already finished or already
      been cancelled. This is the literal shape of this ticket's
      acceptance criterion ("cancelling an already-finished or
      already-cancelled run does not raise") without silently accepting
      an arbitrary unknown id as if it were a real, tracked run.
    - The per-run queue carries a `None` sentinel appended after the
      run's background task finishes draining `run_streaming()`, for any
      reason: the run completed normally (its own terminal `done` event
      was already put on the queue before the sentinel), it crashed
      (`run_streaming()` itself never raises; see its own docstring, so
      this path is the normal "finished" case even after an internal
      crash, not a separate failure mode here), or it was cancelled. A
      queue consumer (a later ticket's SSE endpoint) reads until it sees
      `None` and then closes the stream, rather than needing to inspect
      the task's own state directly.
    - No lock guards `RunRegistry._runs`. Every mutation (`create_run`
      inserting an entry, `cancel_run` reading one) runs on the single
      asyncio event loop thread, and CPython's GIL makes a single dict
      `__setitem__`/`__getitem__` atomic against another coroutine
      interleaving mid-operation; `Harness.track_cost`'s `threading.Lock`
      exists for a different reason (protecting a shared dict that
      genuinely may be touched from multiple OS threads), which does not
      apply here.
    - T-1.2-02 cross-ticket addition: `create_run` gained an optional,
      keyword-only `run_id` parameter (default `None`, preserving every
      existing call site's behavior unchanged). See `create_run`'s own
      docstring for the full rationale; in short, it lets an HTTP endpoint
      mint the run's id once, thread it through `Query.trace_id` before
      this call, and pass it back in here, so the returned `run_id` and
      the `trace_id` on every event this run produces are always the same
      value rather than two independently-minted ones.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from system_03_search_agent.contracts.events import Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run_streaming


class RunNotFoundError(KeyError):
    """Raised by `get_run`/`cancel_run` for a `run_id` this registry never created.

    Subclasses `KeyError` (the natural fit for a dict-backed lookup miss)
    but is given its own name so a caller can catch it specifically
    without also swallowing an unrelated `KeyError` bug elsewhere in the
    same `try` block. A later ticket's endpoint catches this and returns
    `404`.
    """

    def __init__(self, run_id: str) -> None:
        super().__init__(run_id)
        self.run_id = run_id

    def __str__(self) -> str:
        return f"no run registered with run_id {self.run_id!r}"


@dataclass
class RunEntry:
    """One tracked run: its id, its owner, its event queue, and its background task."""

    run_id: str
    user_id: str | None
    queue: "asyncio.Queue[Event | None]" = field(repr=False)
    task: "asyncio.Task[None]" = field(repr=False)


async def _drain_into_queue(
    query: Query, context: RequestContext, queue: "asyncio.Queue[Event | None]"
) -> None:
    """Background task body: run the streaming graph, push every event
    into `queue` as it arrives, then push the `None` end-of-stream
    sentinel.

    `run_streaming()` never raises (its own docstring; any otherwise-
    uncaught graph exception is already converted into a terminal
    `error`/`done` event pair), so the only way this coroutine itself
    ends abnormally is external cancellation (`cancel_run`), which raises
    `asyncio.CancelledError` here. The `finally` block still runs on a
    cancellation, so the sentinel is still pushed and a queue consumer
    still sees a clean end-of-stream rather than hanging forever waiting
    for one more item that will never arrive.
    """
    try:
        async for event in run_streaming(query, context):
            await queue.put(event)
    finally:
        await queue.put(None)


class RunRegistry:
    """In-process registry of streaming runs. See the module docstring."""

    def __init__(self) -> None:
        self._runs: dict[str, RunEntry] = {}

    def create_run(
        self, query: Query, context: RequestContext, *, run_id: str | None = None
    ) -> str:
        """Mint a `run_id` (or accept a caller-provided one), start
        `run_streaming(query, context)` as a background task draining into
        a fresh per-run queue, and record `query.user_id` as the run's
        owner.

        Returns the new `run_id` immediately; the background task has not
        necessarily produced any events yet by the time this returns (by
        design: the caller, e.g. a `POST /v1/query` endpoint, responds
        `202` with the `run_id` right away, per Section 13.1's intent).

        Args:
            run_id: T-1.2-02 cross-ticket addition. Section 13.1 frames
                `run_id` and `Query.trace_id` as "the same identifier
                under two names", so the HTTP layer that builds `query`
                needs to know the run's id *before* this call, in order
                to set `query.trace_id` to it. This module originally
                always minted its own id and had no way to honor one
                chosen upstream, which would have forced a mismatch
                between the returned `run_id` and the `trace_id` woven
                through every event `run_streaming` produces, breaking
                `trace_id`'s role as the single join key across
                LangSmith, the interactions table, and the audit log
                (production-standards.md). Passing `run_id` here closes
                that gap: the endpoint mints one `uuid.uuid4()`, builds
                `query` with `trace_id` set to it, then passes the same
                value through so the id this method returns is always
                byte-identical to `query.trace_id`, never a second,
                independently-minted id. Left as `None` (the default),
                this method mints its own id exactly as before, so every
                existing caller (including this file's own test suite)
                is unaffected.
        """
        resolved_run_id = run_id if run_id is not None else str(uuid.uuid4())
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        task = asyncio.create_task(_drain_into_queue(query, context, queue))
        self._runs[resolved_run_id] = RunEntry(
            run_id=resolved_run_id, user_id=query.user_id, queue=queue, task=task
        )
        return resolved_run_id

    def get_run(self, run_id: str) -> RunEntry:
        """Look up a run's queue, owner, and background task by `run_id`.

        Raises:
            RunNotFoundError: `run_id` was never created by this registry.
        """
        try:
            return self._runs[run_id]
        except KeyError:
            raise RunNotFoundError(run_id) from None

    def cancel_run(self, run_id: str) -> None:
        """Cancel `run_id`'s background task.

        Idempotent for a known run: calling this on a run whose task has
        already finished (successfully or not) or has already been
        cancelled is a no-op, never raising, matching the
        production-standards.md retry-safety gate ("writes must be
        idempotent or repeat-safe"). `asyncio.Task.cancel()` itself is
        already a no-op (it simply returns `False`) when called on a
        task that is already done, so no extra state check is required
        to satisfy that half of idempotency; it is spelled out explicitly
        below anyway so the idempotent case is visible at a glance rather
        than relying on an unstated property of `asyncio.Task`.

        Raises:
            RunNotFoundError: `run_id` was never created by this
                registry at all (as opposed to having finished or already
                been cancelled, which is the idempotent no-op case
                above).
        """
        entry = self.get_run(run_id)
        if not entry.task.done():
            entry.task.cancel()


# Module-level default instance. Per the module docstring, this registry
# is in-process, module-level state; a single shared instance is what a
# later ticket's FastAPI app (one process, one event loop for this phase)
# imports and uses, without every call site needing to construct or thread
# its own `RunRegistry`. Tests construct their own `RunRegistry()` instances
# to stay isolated from one another rather than sharing this default.
default_registry = RunRegistry()
