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
    - Abandonment (F-1.2-02): a run is cancelled once its CUMULATIVE
      unwatched time (real seconds with zero attached subscribers, summed
      across every unwatched interval, not reset by a brief reconnect)
      reaches `abandon_grace_seconds` (default 30). The grace period
      exists so a briefly dropped connection (Section 13.1's own framing:
      "a CLI session on a flaky connection or a browser tab that was
      backgrounded") gets a real chance to reconnect before the run
      underneath it is killed, rather than the first disconnect ending
      the run outright. Tracking cumulative rather than resettable time
      is a fix-round addition (F-4.0-A-01, adversary round 1): a naive
      full-reset-on-every-reconnect timer let a churn of brief
      attach/detach cycles under the grace window hold a run alive
      forever, since each reconnect discarded whatever unwatched time had
      already accumulated.
    - Multi-consumer (F-1.2-03): see `subscribe()` above; this was the
      concrete, reproduced shape of the resumability gap the phase 1.2
      Scope note had already named as deferred to this phase.

    Known open gap, carried rather than fixed this round (F-4.0-A-14,
    adversary round 1): abandonment's definition of "watched" is
    "a subscriber is attached" (`subscriber_count > 0`), never "a
    subscriber is actually reading". A connection that attaches and never
    reads a byte (an idle socket, deliberate or not) holds
    `subscriber_count` above zero forever and suppresses the check
    entirely, which the cumulative-time fix above does not touch, since
    it only ever counts time spent at `subscriber_count == 0`. Closing
    this needs delivery-based liveness (each subscriber proving forward
    progress, e.g. a per-subscriber idle-read timeout), a materially
    bigger change than the timer-accounting fix above, and is carried to
    `tracker/phase_4.0.md`'s Open items rather than rushed into the same
    round that just changed this exact concurrency-sensitive method.

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
      protocol. Almost every mutation runs on the single asyncio event
      loop thread with no `await` between a read and the write it
      informs, so CPython's GIL makes each individual mutation atomic
      against another coroutine interleaving mid-operation; asyncio's own
      cooperative scheduling (a coroutine only yields control at an
      `await`) means a concurrently-running reader can never observe a
      torn intermediate state, only a stale one it will catch up on via
      the next `new_event.notify_all()`. `new_event`'s lock is held only
      where the `asyncio.Condition` API requires it (`wait_for`,
      `notify_all`), not as a general-purpose mutex around every field
      access.

      CORRECTION, build phase 4.10 fix round 1 (F-4.10-J-03): "every
      mutation runs on the single asyncio event loop thread" became FALSE
      the moment `reassign_owner` shipped. Its only caller is
      `auth/router.py`'s `_migrate_guest_session`, reached from `POST
      /auth/signup` and `POST /auth/login`, and both of those path
      operations are plain `def`, which FastAPI dispatches to an AnyIO
      worker thread. So `reassign_owner` mutates `_runs` entries from a
      thread that is NOT the event loop, concurrently with `create_run`
      inserting into the same dict from the loop, and the sentence above
      no longer covers it. A stale read is still harmless here for the
      same GIL reason, but an UNGUARDED `for entry in self._runs.values()`
      is not: it raises `RuntimeError: dictionary changed size during
      iteration` when an insert lands mid-sweep. Every method that walks
      `_runs` (`_evict_expired`, `count_active_runs_for_owner`,
      `reassign_owner`) therefore materialises the dict with a single
      `list(...)`/`tuple(...)` call before walking it. That call is one
      C-level operation, so the GIL makes it atomic against another
      thread's insert, and the walk that follows is over a private
      snapshot no other thread can resize. This is a bound on the ONE
      real cross-thread shape that exists today; it is not a claim that
      this registry is generally thread-safe, and it does not make the
      registry safe across processes (see the eviction note above and
      `tracker/phase_4.10.md`'s stated non-coverage).
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
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from system_03_search_agent.contracts.events import ErrorPayload, Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run_streaming

logger = logging.getLogger(__name__)

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

# T-4.10-05 (design decision 7, tracker/phase_4.10.md): the per-principal
# concurrent-run cap that closes F-4.0-A-10. F-4.0-A-10 measured 9,615
# runs created by ONE caller in roughly 50 seconds of bursts, with zero
# rejections, because nothing bounded run creation at all. This constant
# bounds concurrently ACTIVE (not yet `finished`) runs per owner_id, not a
# cumulative rate: a legitimate caller (one browser tab, plus perhaps a
# stray reconnect or a deliberate follow-up question fired before the
# first answer lands) is not expected to have more than a couple of runs
# genuinely in flight at once. 5 gives headroom above that ordinary shape
# while still cutting the unbounded-burst pattern off completely; it is a
# v1 engineering call, not a value derived from a load test (the real
# per-layer throttling and concurrency-queue strategy is build phase
# 6.0's job, tool-call-budgets.md).
DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER = 5

# A conservative, static hint, not a promise: a caller that hits this cap
# is told to retry in a few seconds, which is comfortably longer than a
# guard/plan/synth round trip normally takes to free a slot by finishing,
# but this module has no per-run completion-time estimate to compute a
# tighter number from. Genuinely transient (design decision 5): finishing
# or stopping an existing run frees a slot immediately, unlike the guest
# allowance's 403, which retrying can never fix.
CONCURRENT_RUN_CAP_RETRY_AFTER_S = 5


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


class ConcurrentRunCapExceededError(RuntimeError):
    """Raised by `RunRegistry.create_run` when `owner_id` already has
    `DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER` (or the registry's configured
    override) active runs (T-4.10-05, closes F-4.0-A-10).

    Genuinely transient (design decision 5, tracker/phase_4.10.md):
    finishing or stopping an existing run frees a slot immediately, so the
    HTTP layer maps this to `429` with a real `Retry-After`, never the
    guest-allowance-exhausted `403` that retrying can never fix.
    """

    def __init__(self, message: str, *, retry_after_s: int) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


@dataclass
class RunEntry:
    """One tracked run: its id, its owner, both read paths, and its
    background task."""

    run_id: str
    user_id: str | None
    # T-4.10-03, design decision 2 (tracker/phase_4.10.md): the namespaced
    # identity ("user:<uuid>" or "guest:<uuid>") every ownership
    # comparison reads (adapters/web_sse/app.py's `_get_owned_run`).
    # `user_id` above is left untouched, the bare registered-user UUID
    # string or None, because it is what `is_operator_user()` and a
    # future `interactions.user_id` write need; a namespaced string must
    # never reach either.
    owner_id: str
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
    # F-4.0-A-01 (adversary round 1, build phase 4.0): real seconds this
    # run has spent with zero subscribers attached, summed across every
    # unwatched interval rather than reset by each new one.
    # `unwatched_since` is when the CURRENT unwatched interval began, or
    # `None` while at least one subscriber is attached. See
    # `RunRegistry._reschedule_abandonment_check` for how these two
    # fields close the churn bypass: cancelling and rescheduling a
    # fresh full-length timer on every subscribe/unsubscribe let a
    # reconnect cadence shorter than the grace window hold a run alive
    # forever, because each reset discarded whatever unwatched time had
    # already accumulated.
    cumulative_unwatched_seconds: float = 0.0
    unwatched_since: datetime | None = None
    # F-4.0-A-04 (adversary round 1, build phase 4.0): set the moment
    # `_drain_into_entry` observes `asyncio.CancelledError`, distinct from
    # `finished`, which a cancellation and a normal completion both set
    # identically. The HTTP layer reads this to disclose a cancelled run's
    # citation export as partial rather than indistinguishable from a
    # genuinely empty one (F-4.0-A-05).
    cancelled: bool = False
    # F-4.10-A-04 (adversary round 1, build phase 4.10): fired at most once,
    # by `_drain_into_entry`, the first time this run emits a `guard` event
    # with `passed: false`. This registry knows nothing about allowances and
    # must not: the callback is supplied by whoever created the run (the web
    # surface passes one only for a guest caller), so the refund policy lives
    # at the layer that owns the allowance and this module only reports the
    # observation. Set back to `None` the instant it fires, which is what
    # makes "at most once per run" structural rather than a convention.
    on_guard_refused: Callable[[], None] | None = field(default=None, repr=False)


def _fire_guard_refusal_callback(entry: RunEntry, event: Event) -> None:
    """Invoke `entry.on_guard_refused` the first time this run refuses at the
    guardrail, then disarm it (F-4.10-A-04).

    WHERE A GUARD REFUSAL BECOMES OBSERVABLE, and why it is here. The
    guardrail runs inside the agent loop, long after `POST /v1/query` has
    already returned `202` and already spent the caller's allowance. There is
    no earlier point: `core/graph.py`'s `_decline_for_guardrail` emits a
    `guard` event carrying `passed: false` and then stops the graph, and this
    drain loop is the first thing outside the graph that sees any event at
    all. So the compensation is a refund after the fact, never a deferred
    charge. Moving the spend to after the guardrail was considered and
    rejected: it would let a caller start unbounded runs that never spend at
    all, which is a strictly worse hole than the one being closed.

    A `guard` event with `passed: false` is the ONLY signal used, rather than
    "the run produced no answer". A refusal is a judgement the system reached,
    distinct from an error, which `_decline_for_guardrail`'s own docstring
    already insists on; a failed run is a different question with a different
    answer and is not in scope here.

    Never raises. A callback that fails must not turn a correctly refused run
    into a crashed one, and the caller's own allowance is the thing at stake,
    not the run.
    """
    callback = entry.on_guard_refused
    if callback is None or event.type != "guard" or event.payload.get("passed") is not False:
        return
    # Disarm BEFORE calling, not after: a callback that raises must still
    # have consumed its one shot, or a later `guard` event (there is none
    # today, and relying on that is how a second refund gets written) could
    # fire it again.
    entry.on_guard_refused = None
    try:
        callback()
    except Exception:  # noqa: BLE001 - a refund failure must never fail the run
        # No exc_info and no interpolated values, per production-standards'
        # secrets gate: a database exception's own string can embed bound
        # parameters, and the guest id is one of them.
        logger.warning(
            "the guard-refusal callback for run %s failed; the caller was "
            "charged for a refused run",
            entry.run_id,
        )


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

    F-4.0-A-04 (adversary round 1, build phase 4.0): a cancellation used
    to reach the `finally` block below with no event of its own, so a
    client watching the stream saw it simply stop after the last real
    event, indistinguishable from a dropped connection. The `except`
    clause below gives cancellation the same treatment `run_streaming()`
    already gives a genuine internal failure: a real terminal event,
    appended to both read paths before `finished` is set, so `subscribe`'s
    existing terminal-event check (a fatal `error`) ends the stream on it
    exactly as it would for any other fatal error.
    """
    entry = registry._runs[run_id]
    try:
        async for event in run_streaming(query, context):
            entry.events.append(event)
            await entry.queue.put(event)
            _fire_guard_refusal_callback(entry, event)
            async with entry.new_event:
                entry.new_event.notify_all()
    except asyncio.CancelledError:
        entry.cancelled = True
        cancellation_event = Event(
            type="error",
            version="v1",
            trace_id=query.trace_id,
            seq=len(entry.events),
            ts=datetime.now(UTC),
            payload=ErrorPayload(
                fatal=True,
                scope="run",
                source="run_registry",
                error_class="cancelled",
                message="this run was stopped before it finished",
                retry_after_s=0,
            ).model_dump(),
        )
        entry.events.append(cancellation_event)
        await entry.queue.put(cancellation_event)
        async with entry.new_event:
            entry.new_event.notify_all()
        raise
    finally:
        entry.finished = True
        entry.finished_at = datetime.now(UTC)
        # F-4.0-A-07 (adversary round 1, build phase 4.0): a pending
        # abandonment check used to keep sleeping for up to a full grace
        # window after the run it watches has already ended, since
        # nothing told it the run was over until it woke up on its own
        # and found `task.done()` true. Cancelling it here, the instant
        # the run actually ends, removes that dangling sleeper rather
        # than waiting for it to expire on its own; at the churn rates
        # F-1.2-01 measured, that is the difference between a handful of
        # live sleeping tasks and hundreds.
        if entry.abandonment_check is not None and not entry.abandonment_check.done():
            entry.abandonment_check.cancel()
            entry.abandonment_check = None
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
        max_active_runs_per_owner: int = DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER,
    ) -> None:
        self._runs: dict[str, RunEntry] = {}
        self._retention_seconds = retention_seconds
        self._abandon_grace_seconds = abandon_grace_seconds
        self._max_active_runs_per_owner = max_active_runs_per_owner

    def _evict_expired(self) -> None:
        """Drop every run finished for longer than `retention_seconds`
        (F-1.2-01). Swept lazily; see the module docstring for why no
        separate background sweep task exists."""
        now = datetime.now(UTC)
        # `list(...)` first, then walk the snapshot: see the module
        # docstring's F-4.10-J-03 correction for why walking `_runs`
        # directly is no longer safe.
        expired = [
            run_id
            for run_id, entry in list(self._runs.items())
            if entry.finished_at is not None
            and (now - entry.finished_at).total_seconds() > self._retention_seconds
        ]
        for run_id in expired:
            entry = self._runs.pop(run_id)
            if entry.abandonment_check is not None and not entry.abandonment_check.done():
                entry.abandonment_check.cancel()

    def _reschedule_abandonment_check(self, entry: RunEntry) -> None:
        """Cancel any pending abandonment check, then schedule a fresh one
        against `entry`'s TOTAL unwatched time if it currently has zero
        subscribers and is still running (F-1.2-02). Called whenever
        `subscriber_count` changes and once at `create_run` (a run that
        never gets a first subscriber is the same wasted-cost shape as one
        that had a subscriber and lost it).

        F-4.0-A-01 (adversary round 1, build phase 4.0): the original
        version of this method scheduled a brand new full-length
        `abandon_grace_seconds` timer on every call, discarding whatever
        unwatched time had already accumulated. A reconnect cadence
        shorter than the grace window (attach, detach, repeat) reset the
        clock every time and could hold a run alive forever, defeating
        this method's entire purpose. The fix tracks cumulative real
        unwatched seconds on the entry itself
        (`cumulative_unwatched_seconds`, `unwatched_since`) and schedules
        only the REMAINING budget, so a churn of brief reconnects still
        accumulates real unwatched time between cycles and the run is
        still cancelled once the total crosses the grace window, the same
        outcome as if nobody had ever reconnected at all.
        """
        if entry.abandonment_check is not None:
            entry.abandonment_check.cancel()
            entry.abandonment_check = None

        now = datetime.now(UTC)
        if entry.subscriber_count > 0:
            # Someone is attached: close out the current unwatched
            # interval, if one was open, folding its real duration into
            # the running total, and stop counting until the next detach.
            if entry.unwatched_since is not None:
                entry.cumulative_unwatched_seconds += (
                    now - entry.unwatched_since
                ).total_seconds()
                entry.unwatched_since = None
            return

        if entry.task.done():
            return
        if entry.unwatched_since is None:
            entry.unwatched_since = now
        elapsed_this_interval = (now - entry.unwatched_since).total_seconds()
        remaining = (
            self._abandon_grace_seconds
            - entry.cumulative_unwatched_seconds
            - elapsed_this_interval
        )
        entry.abandonment_check = asyncio.create_task(
            self._cancel_if_still_abandoned(entry.run_id, max(remaining, 0.0))
        )

    async def _cancel_if_still_abandoned(self, run_id: str, delay_seconds: float) -> None:
        await asyncio.sleep(delay_seconds)
        entry = self._runs.get(run_id)
        if entry is None:
            return
        if entry.subscriber_count == 0 and not entry.task.done():
            entry.task.cancel()

    @property
    def max_active_runs_per_owner(self) -> int:
        """The configured concurrent-run cap this instance enforces
        (T-4.10-05). Exposed read-only so a caller (the HTTP layer's own
        precheck) can report or compare against the same value `create_run`
        itself enforces, without reaching into a private attribute."""
        return self._max_active_runs_per_owner

    def count_active_runs_for_owner(self, owner_id: str) -> int:
        """Count `owner_id`'s currently ACTIVE (not yet `finished`) runs.

        T-4.10-05 (closes F-4.0-A-10): a completed run does not count
        against the concurrent-run cap, matching F-1.2-01's own eviction
        fix's framing of "how long", not "how many at once". Public so the
        HTTP layer (`adapters/web_sse/app.py`'s `POST /v1/query`) can
        check this BEFORE spending a guest's allowance (design decision
        4/5's ordering: a refused creation must not spend), while
        `create_run` below still enforces the cap itself as the actual
        authority a caller cannot bypass by skipping this precheck.
        """
        self._evict_expired()
        # Snapshot before counting, per the module docstring's F-4.10-J-03
        # correction.
        return sum(
            1
            for entry in list(self._runs.values())
            if entry.owner_id == owner_id and not entry.finished
        )

    def reassign_owner(
        self, *, old_owner_id: str, new_owner_id: str, new_user_id: str | None
    ) -> int:
        """Re-point every LIVE `RunEntry`'s `owner_id` (and `user_id`)
        from `old_owner_id` to `new_owner_id` (T-4.10-06, design decision
        4: migration moves what actually exists).

        Nothing persists a run today (this registry is in-memory and
        evicts, per the module docstring), so this only ever reaches runs
        this process still holds; it is not, and does not claim to be,
        durable cross-reload history (F-4.10-01). Idempotent by
        construction: a run already reassigned away from `old_owner_id`
        (or evicted) is simply not matched on a second call with the same
        arguments, so a replayed migration is a clean no-op here too.

        Cross-guest isolation (T-4.10-06 acceptance criterion) holds by
        construction at the CALLER, not here: this method reassigns
        exactly what `old_owner_id` names, and the caller (`auth/router.
        py`'s `_migrate_guest_session`) builds `old_owner_id` only from
        the `guest_id` claim decoded out of the presented token itself,
        so a guest token can never name any owner_id but its own.

        THREADING (F-4.10-J-03, build phase 4.10 fix round 1). This is the
        one `_runs` walker that does NOT run on the event loop thread. Its
        only caller, `auth/router.py`'s `_migrate_guest_session`, is
        reached from `POST /auth/signup` and `POST /auth/login`, which are
        plain `def` path operations and so run on an AnyIO worker thread,
        concurrently with `create_run` inserting into `_runs` from the
        loop. Walking `self._runs.values()` directly raised `RuntimeError:
        dictionary changed size during iteration` in that window
        (reproduced, not hypothesised). The `list(...)` below takes a
        snapshot in one atomic C-level call first; the entries it holds
        are the same live objects, so the reassignment still lands on real
        runs, and a run created after the snapshot simply is not matched,
        which is indistinguishable from one created a microsecond after
        this method returned. See the module docstring for the full
        correction to the no-lock invariant this broke.

        Returns:
            The number of entries reassigned, for the caller to log.
        """
        reassigned = 0
        for entry in list(self._runs.values()):
            if entry.owner_id == old_owner_id:
                entry.owner_id = new_owner_id
                entry.user_id = new_user_id
                reassigned += 1
        return reassigned

    def create_run(
        self,
        query: Query,
        context: RequestContext,
        *,
        run_id: str | None = None,
        owner_id: str | None = None,
        on_guard_refused: Callable[[], None] | None = None,
    ) -> str:
        """Mint a `run_id` (or accept a caller-provided one), start
        `run_streaming(query, context)` as a background task feeding both
        read paths, and record the run's owner.

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
            owner_id: the namespaced `user:<uuid>`/`guest:<uuid>` identity
                every ownership comparison reads (T-4.10-03, design
                decision 2). Callers that authenticate through
                `get_caller` (the web_sse surface, T-4.10-03) always pass
                this explicitly. Left as `None` for backward compatibility
                with call sites that predate this ticket (every existing
                test in `test_run_registry.py`/`test_phase_4_0_premise.
                py`, and the MCP surface's own authenticated-user-only
                path, `adapters/mcp/server.py`, T-4.1-03): this method
                then derives `"user:<uuid>"` from `query.user_id` when one
                is present, or a synthetic per-call unique owner_id when
                it is not, so two independently-anonymous callers in two
                different tests never accidentally share a concurrency
                slot.
            on_guard_refused: called at most once, from the background
                task, the first time this run emits a `guard` event with
                `passed: false` (F-4.10-A-04). The web surface passes a
                guest-allowance refund here; every other caller leaves it
                `None` and nothing fires. This registry deliberately holds
                no opinion about what a refusal should cost: it reports the
                observation, and the layer that owns the allowance decides.

        Raises:
            ConcurrentRunCapExceededError: if `owner_id` (resolved or
                derived) already has `max_active_runs_per_owner` runs
                active. T-4.10-05, closes F-4.0-A-10.
        """
        self._evict_expired()
        resolved_run_id = run_id if run_id is not None else str(uuid.uuid4())
        resolved_owner_id = owner_id
        if resolved_owner_id is None:
            resolved_owner_id = (
                f"user:{query.user_id}" if query.user_id is not None else f"anon:{resolved_run_id}"
            )

        # T-4.10-05 (closes F-4.0-A-10): the authoritative enforcement
        # point. Checked here, as the very first thing after resolving
        # owner_id and before the RunEntry is constructed, so the same
        # single-threaded, no-await-in-between atomicity this module's own
        # docstring already documents for every other `_runs` mutation
        # covers this check too: nothing can observe or mutate `_runs`
        # between this count and the entry insertion below within one
        # process. This bounds concurrently active runs; it is a distinct
        # control from the guest allowance's own atomicity, which
        # `data.guest_sessions.spend_one_run`'s conditional `UPDATE`
        # guarantees independently at the database layer, and it does not
        # (and cannot, being in-process, per this module's own stated
        # non-coverage) close a true multi-process race, only the
        # single-caller unbounded-burst shape F-4.0-A-10 measured.
        active = self.count_active_runs_for_owner(resolved_owner_id)
        if active >= self._max_active_runs_per_owner:
            raise ConcurrentRunCapExceededError(
                f"owner {resolved_owner_id!r} already has {active} run(s) in "
                f"flight, at the cap of {self._max_active_runs_per_owner}; "
                "wait for an existing run to finish, or stop one via "
                "POST /v1/query/{run_id}/stop, then retry",
                retry_after_s=CONCURRENT_RUN_CAP_RETRY_AFTER_S,
            )

        entry = RunEntry(
            run_id=resolved_run_id,
            user_id=query.user_id,
            owner_id=resolved_owner_id,
            queue=asyncio.Queue(),
            task=asyncio.create_task(
                _drain_into_entry(self, resolved_run_id, query, context)
            ),
            on_guard_refused=on_guard_refused,
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
