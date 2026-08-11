"""In-process run registry: T-1.2-01, `tracker/phase_1.2.md`. Rebuilt at
build phase 4.0 (`tracker/phase_4.0.md`) into the finalized shape Section
13.1 describes.

Tracks every in-flight (or recently finished) streaming run so the HTTP
surface (`POST /v1/query`, `GET /v1/query/{run_id}/events`, `GET
/v1/query/{run_id}/citations`, `POST /v1/query/{run_id}/stop`) can create a
run, hand a client back a `run_id` immediately, let any number of clients
(the original caller, a reconnect after a dropped connection, or a second
concurrent caller) attach to the run's event stream from any point in its
history, and stop a run on request.

Two read paths coexist deliberately:

    - `RunEntry.queue`: the original phase 1.2 mechanism, a single
      `asyncio.Queue[Event | None]` fed by the background task, drained
      destructively by exactly one consumer until the `None` sentinel. As
      of build phase 4.0, no shipped HTTP path reads it any more (`GET
      /events` moved to `subscribe()` below); it is retained solely
      because build phase 1.2's existing tests reach into `entry.queue`
      directly to make internal assertions, and narrowing an existing
      verify surface as a side effect of an unrelated change is exactly
      what `.claude/rules/goal-contracts.md` forbids. Concretely: every
      event is still appended here alongside `events` (see
      `_drain_into_entry`), so the two buffers coexist and consume memory
      together for a run's lifetime, bounded by the same eviction window;
      this is intentional test-fixture support, not a leak (F-4.0-J-05,
      judge review, build phase 4.0).
    - `RunEntry.events` plus `subscribe()`: the new multi-consumer,
      resumable read path this phase adds. `events` is an append-only,
      `seq`-ordered buffer of everything the run has produced so far;
      `subscribe(run_id, after_seq)` replays whatever is already buffered
      past `after_seq` and then follows the live tail, coordinated via
      `RunEntry.new_event` (an `asyncio.Condition`), until a terminal event
      is yielded. Any number of independent subscribers can attach to the
      same run at once, each with its own cursor (F-1.2-03), and a
      reconnecting client's `Last-Event-ID` becomes `after_seq` (Section
      13.1's resumability).

Both paths are fed by the same background task, from the same
`run_streaming()` iteration; neither is a copy of the other's data, they
are two independent views over the one real event sequence.

Three further behaviors, closing the three findings an adversary run filed
against the phase 1.2 shape (F-1.2-01/02/03, `LEARNINGS.md`'s 2026-07-28
entry):

    - Eviction (F-1.2-01): a finished run's entry (its buffered `events`,
      its drained `queue`, its completed `task`) is dropped once it has
      been finished for longer than `retention_seconds` (default 300,
      Section 13.1's "the run's lifetime plus five minutes"). Swept lazily
      at the top of `create_run` and `get_run`, not by a scheduled
      background sweep task; this is a single-process, low-enough-traffic
      v1 registry (this module's own long-standing scope note), and every
      caller-facing entry point already touches the registry once per
      call, which is enough to bound staleness to "since the last call",
      not a fixed clock tick. Load-scale behavior under real concurrency
      is build phase 6.0's job (`tracker/phase_4.0.md`'s stated exclusion),
      not this module's.
    - Abandonment (F-1.2-02): a run with zero attached subscribers,
      whether because every subscriber disconnected or because none ever
      attached, is cancelled `abandon_grace_seconds` (default 30) after
      the last subscriber count reaches zero, unless a new subscriber
      attaches first. The grace period exists so a briefly dropped
      connection (Section 13.1's own framing: "a CLI session on a flaky
      connection or a browser tab that was backgrounded") gets a real
      chance to reconnect before the run underneath it is killed, rather
      than the first disconnect ending the run outright.
    - Multi-consumer (F-1.2-03): see `subscribe()` above; this was the
      concrete, reproduced shape of the resumability gap the phase 1.2
      Scope note had already named as deferred to this phase.

Depends on:
    - system_03_search_agent.core.run (run_streaming)
    - system_03_search_agent.contracts.events (Event)
    - system_03_search_agent.contracts.query (Query, RequestContext)

Reads:
    - Nothing directly.

Writes:
    - Nothing directly. All state lives in the `RunRegistry` instance's
      own in-process dict and the `asyncio.Queue`/`asyncio.Task`/
      `asyncio.Condition` objects it creates.

Design decisions carried unchanged from phase 1.2, made here rather than
asked about, per this ticket's instruction to make the most reasonable
engineering call and document it:

    - Ownership is derived from `query.user_id`, not passed as a separate
      parameter (see the HTTP layer, T-2.0-08).
    - `get_run` raises the named `RunNotFoundError` for an unknown
      `run_id`, rather than returning `None`, so a 404-versus-403 branch
      is explicit at the call site.
    - `cancel_run` also raises `RunNotFoundError` for a genuinely unknown
      `run_id`, but is a no-op, never raising, for a `run_id` that exists
      but whose background task has already finished or already been
      cancelled (production-standards.md's retry-safety gate).
    - No lock guards `RunRegistry._runs`, `RunEntry.events`, or the
      `finished`/`finished_at` fields outside of `new_event`'s own
      protocol. Every mutation runs on the single asyncio event loop
      thread with no `await` between a read and the write it informs, so
      CPython's GIL makes each individual mutation atomic against another
      coroutine interleaving mid-operation; asyncio's own cooperative
      scheduling (a coroutine only yields control at an `await`) means a
      concurrently-running reader can never observe a torn intermediate
      state, only a stale one it will catch up on via the next
      `new_event.notify_all()`. `new_event`'s lock is held only where the
      `asyncio.Condition` API requires it (`wait_for`, `notify_all`), not
      as a general-purpose mutex around every field access.
    - The per-run queue still carries a `None` sentinel appended after the
      run's background task finishes draining `run_streaming()`, for any
      reason: normal completion, an internal crash (already converted to
      a terminal `error`/`done` pair inside `run_streaming()` itself, per
      its own docstring), or cancellation. `entry.finished`/
      `entry.finished_at` are set at the same point, guarded by the same
      `finally` block, so both read paths agree on when a run ended.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

from system_03_search_agent.contracts.events import Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run_streaming

# Section 13.1: "the server buffers each run's emitted events... for the
# run's lifetime plus five minutes". Module-level default so it is visible
# without reading `RunRegistry.__init__`; overridable per-instance for
# tests that need eviction to fire without a real five-minute wait.
DEFAULT_RETENTION_SECONDS = 300.0

# Not spec'd by Section 13.1 (which names the resumability window but not
# an abandonment timeout); a made-and-recorded engineering call, sized to
# "a briefly dropped connection reconnects within seconds, not minutes",
# the same flaky-connection framing Section 13.1 gives resumability itself.
DEFAULT_ABANDON_GRACE_SECONDS = 30.0


class RunNotFoundError(KeyError):
    """Raised by `get_run`/`cancel_run`/`subscribe` for a `run_id` this
    registry never created, or one it has since evicted.

    Subclasses `KeyError` (the natural fit for a dict-backed lookup miss)
    but is given its own name so a caller can catch it specifically
    without also swallowing an unrelated `KeyError` bug elsewhere in the
    same `try` block. The HTTP layer catches this and returns `404`.
    """

    def __init__(self, run_id: str) -> None:
        super().__init__(run_id)
        self.run_id = run_id

    def __str__(self) -> str:
        return f"no run registered with run_id {self.run_id!r}"


@dataclass
class RunEntry:
    """One tracked run: its id, its owner, both read paths, and its
    background task."""

    run_id: str
    user_id: str | None
    queue: asyncio.Queue[Event | None] = field(repr=False)
    task: asyncio.Task[None] = field(repr=False)
    events: list[Event] = field(default_factory=list, repr=False)
    new_event: asyncio.Condition = field(default_factory=asyncio.Condition, repr=False)
    finished: bool = False
    finished_at: datetime | None = None
    subscriber_count: int = 0
    # Handle for a pending "cancel this run if still unwatched" check,
    # scheduled by `RunRegistry._reschedule_abandonment_check`. `None`
    # whenever at least one subscriber is attached, or the run is already
    # finished, or no check has been scheduled yet.
    abandonment_check: asyncio.Task[None] | None = field(default=None, repr=False)


async def _drain_into_entry(
    registry: RunRegistry, run_id: str, query: Query, context: RequestContext
) -> None:
    """Background task body: run the streaming graph, feed every event
    into both of `run_id`'s read paths as it arrives, then mark the run
    finished.

    Looks `run_id` up in `registry._runs` on its own first line rather
    than receiving the `RunEntry` directly, because `create_run` (see
    below) starts this task before it has anywhere to put the `RunEntry`
    it is about to construct. This is safe without a race: `create_run`
    is not itself a coroutine and never `await`s between calling
    `asyncio.create_task` and inserting the new entry into `_runs`, so a
    freshly created task cannot actually run (asyncio only switches
    coroutines at an `await`) until control returns to the event loop,
    by which point `_runs[run_id]` is already populated.

    `run_streaming()` never raises (its own docstring; any otherwise-
    uncaught graph exception is already converted into a terminal
    `error`/`done` event pair), so the only way this coroutine itself
    ends abnormally is external cancellation, which raises
    `asyncio.CancelledError` here. The `finally` block still runs on a
    cancellation, so both read paths still see a clean end rather than
    hanging forever waiting for one more item that will never arrive.
    """
    entry = registry._runs[run_id]
    try:
        async for event in run_streaming(query, context):
            entry.events.append(event)
            await entry.queue.put(event)
            async with entry.new_event:
                entry.new_event.notify_all()
    finally:
        entry.finished = True
        entry.finished_at = datetime.now(UTC)
        async with entry.new_event:
            entry.new_event.notify_all()
        await entry.queue.put(None)


class RunRegistry:
    """In-process registry of streaming runs. See the module docstring."""

    def __init__(
        self,
        *,
        retention_seconds: float = DEFAULT_RETENTION_SECONDS,
        abandon_grace_seconds: float = DEFAULT_ABANDON_GRACE_SECONDS,
    ) -> None:
        self._runs: dict[str, RunEntry] = {}
        self._retention_seconds = retention_seconds
        self._abandon_grace_seconds = abandon_grace_seconds

    def _evict_expired(self) -> None:
        """Drop every run finished for longer than `retention_seconds`
        (F-1.2-01). Swept lazily; see the module docstring for why no
        separate background sweep task exists."""
        now = datetime.now(UTC)
        expired = [
            run_id
            for run_id, entry in self._runs.items()
            if entry.finished_at is not None
            and (now - entry.finished_at).total_seconds() > self._retention_seconds
        ]
        for run_id in expired:
            entry = self._runs.pop(run_id)
            if entry.abandonment_check is not None and not entry.abandonment_check.done():
                entry.abandonment_check.cancel()

    def _reschedule_abandonment_check(self, entry: RunEntry) -> None:
        """Cancel any pending abandonment check, then schedule a fresh one
        if `entry` currently has zero subscribers and is still running
        (F-1.2-02). Called whenever `subscriber_count` changes and once at
        `create_run` (a run that never gets a first subscriber is the same
        wasted-cost shape as one that had a subscriber and lost it)."""
        if entry.abandonment_check is not None:
            entry.abandonment_check.cancel()
            entry.abandonment_check = None
        if entry.subscriber_count == 0 and not entry.task.done():
            entry.abandonment_check = asyncio.create_task(self._cancel_if_still_abandoned(entry.run_id))

    async def _cancel_if_still_abandoned(self, run_id: str) -> None:
        await asyncio.sleep(self._abandon_grace_seconds)
        entry = self._runs.get(run_id)
        if entry is None:
            return
        if entry.subscriber_count == 0 and not entry.task.done():
            entry.task.cancel()

    def create_run(
        self, query: Query, context: RequestContext, *, run_id: str | None = None
    ) -> str:
        """Mint a `run_id` (or accept a caller-provided one), start
        `run_streaming(query, context)` as a background task feeding both
        read paths, and record `query.user_id` as the run's owner.

        Returns the new `run_id` immediately; the background task has not
        necessarily produced any events yet by the time this returns (by
        design: `POST /v1/query` responds `202` with the `run_id` right
        away, per Section 13.1's intent).

        Args:
            run_id: lets the HTTP layer mint one `uuid.uuid4()`, set
                `query.trace_id` to it, and pass the same value through so
                the id this method returns is always byte-identical to
                `query.trace_id`, never a second, independently-minted id
                (`trace_id`'s "single join key" role, production-
                standards.md). Left as `None`, this method mints its own.
        """
        self._evict_expired()
        resolved_run_id = run_id if run_id is not None else str(uuid.uuid4())
        entry = RunEntry(
            run_id=resolved_run_id,
            user_id=query.user_id,
            queue=asyncio.Queue(),
            task=asyncio.create_task(
                _drain_into_entry(self, resolved_run_id, query, context)
            ),
        )
        self._runs[resolved_run_id] = entry
        self._reschedule_abandonment_check(entry)
        return resolved_run_id

    def get_run(self, run_id: str) -> RunEntry:
        """Look up a run by `run_id`.

        Raises:
            RunNotFoundError: `run_id` was never created by this
                registry, or was created but has since been evicted
                (F-1.2-01: a stale read is a 404, never stale data).
        """
        self._evict_expired()
        try:
            return self._runs[run_id]
        except KeyError:
            raise RunNotFoundError(run_id) from None

    def cancel_run(self, run_id: str) -> None:
        """Cancel `run_id`'s background task.

        Idempotent for a known run: calling this on a run whose task has
        already finished (successfully or not) or has already been
        cancelled is a no-op, never raising, matching the
        production-standards.md retry-safety gate.

        Raises:
            RunNotFoundError: `run_id` was never created by this
                registry at all (as opposed to having finished or already
                been cancelled, which is the idempotent no-op case
                above).
        """
        entry = self.get_run(run_id)
        if not entry.task.done():
            entry.task.cancel()

    async def subscribe(self, run_id: str, *, after_seq: int = -1) -> AsyncIterator[Event]:
        """Yield every event `run_id` has produced with `seq > after_seq`,
        replaying whatever is already buffered and then following the
        live tail, until a terminal event (`done`, or a fatal `error`) is
        yielded or the run ends with no such event.

        `after_seq=-1` (the default) replays the whole history, since
        every real `seq` is `>= 0` (Section 2.2). A reconnecting client
        passes its last-seen `seq` (the HTTP layer's `Last-Event-ID`) to
        resume exactly where it left off, never re-delivering an event it
        already has and never skipping one it does not.

        Any number of calls to this method for the same `run_id`,
        concurrent or sequential, each get their own complete view
        (F-1.2-03); this is the fix for the single-consumer queue, not a
        second copy of it.

        Tracks `entry.subscriber_count` for the duration of iteration
        (incremented on entry, decremented in `finally`, including when
        the caller stops iterating early, e.g. a dropped HTTP connection),
        which feeds `_reschedule_abandonment_check`'s cancel-if-abandoned
        decision (F-1.2-02).

        Raises:
            RunNotFoundError: `run_id` was never created by this
                registry, or has since been evicted.
        """
        entry = self.get_run(run_id)
        async with entry.new_event:
            entry.subscriber_count += 1
            self._reschedule_abandonment_check(entry)
        try:
            last_yielded = after_seq
            while True:
                async with entry.new_event:
                    await entry.new_event.wait_for(
                        # Bind the current `last_yielded` as a default argument
                        # rather than closing over the enclosing loop variable
                        # (ruff B023): `wait_for` may re-invoke this predicate
                        # on every notify while waiting, and `last_yielded`
                        # only changes in the `for` loop below, but binding it
                        # explicitly removes any doubt about which value a
                        # given call sees.
                        lambda seen=last_yielded: entry.finished
                        or any(e.seq > seen for e in entry.events)
                    )
                    pending = [e for e in entry.events if e.seq > last_yielded]
                for event in pending:
                    yield event
                    last_yielded = event.seq
                    if event.type == "done" or (
                        event.type == "error" and event.payload.get("fatal") is True
                    ):
                        return
                if entry.finished and not pending:
                    return
        finally:
            async with entry.new_event:
                entry.subscriber_count -= 1
                self._reschedule_abandonment_check(entry)


# Module-level default instance. Per the module docstring, this registry
# is in-process, module-level state; a single shared instance is what the
# FastAPI app (one process, one event loop for this phase) imports and
# uses, without every call site needing to construct or thread its own
# `RunRegistry`. Tests construct their own `RunRegistry()` instances to
# stay isolated from one another rather than sharing this default.
default_registry = RunRegistry()
