"""Count event loop lag, one WARNING log line each (cards 84 and 72, step 3b).

One background task sleeps in looks of 50 ms and measures, on the monotonic
clock, how late each look returned. A look that returns 0.25 s or more late
(timers ran late) writes one line:

    event loop lag: 0.40 s (timers ran late), began 2026-10-16T09:30:00Z

What the line counts: timers that ran late, which is exactly what a credit for
a slow loop would act on. It does not prove a freeze. Three things produce it:
a frozen loop (one call that blocks), a loop kept busy by several tasks that
each hold it in short chunks, and a host that pauses the whole process. Read
the count as "the loop could not keep its timers", never as freezes only.

How far to trust the figure: the threshold is "timers late by 0.25 s or more",
so a block just over 0.25 s can be missed, and the printed figure can be up to
0.05 s short of the block. The "began" stamp is the start of the look that ran
late, not the start of the block.

Level is WARNING on purpose, the convention `harness/call_log.py` states: the
service configures no root log level of its own, and alembic's `fileConfig`
(run at startup on develop) leaves the root at WARNING, so an INFO line would
be dropped and the count would read zero. The line holds the length and the
start time only, on one physical line. No question text, no user data.

The switch `LOOP_STALL_WATCH` (default on; "0", "false", "off" or "no" turns it
off) needs no code deploy. The watcher never raises into the app.
"""

import asyncio
import contextlib
import logging
import os
import time
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

_LOOK_S = 0.05
_PAUSE_MIN_S = 0.25
_SWITCH_ENV = "LOOP_STALL_WATCH"
_OFF_VALUES = frozenset({"0", "false", "off", "no"})


def watch_enabled() -> bool:
    """True unless the environment switch turns the watcher off."""
    return os.environ.get(_SWITCH_ENV, "1").strip().lower() not in _OFF_VALUES


async def _watch() -> None:
    while True:
        began_wall = time.time()
        began = time.monotonic()
        await asyncio.sleep(_LOOK_S)
        with contextlib.suppress(Exception):  # a counter must never break the app
            late_s = time.monotonic() - began - _LOOK_S
            if late_s >= _PAUSE_MIN_S:
                stamp = datetime.fromtimestamp(began_wall, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                logger.warning("event loop lag: %.2f s (timers ran late), began %s", late_s, stamp)


def start_loop_stall_watch() -> "asyncio.Task[None] | None":
    """Start the watcher on the running loop, or return None when switched off."""
    if not watch_enabled():
        return None
    return asyncio.get_running_loop().create_task(_watch(), name="loop-stall-watch")


async def stop_loop_stall_watch(task: "asyncio.Task[None] | None") -> None:
    """Cancel the watcher and wait for it. Safe with None. Passes on a cancel aimed at the caller."""
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        # The watcher's own cancel is expected. A cancel aimed at our caller is not.
        current = asyncio.current_task()
        if current is not None and current.cancelling() > 0:
            raise
    except Exception:  # noqa: BLE001, S110 - a counter must never break shutdown
        pass
