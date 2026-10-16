"""Count real event loop stalls, one INFO log line each (cards 84 and 72, step 3b).

A "server pause" is a stretch when the event loop runs nothing. One background
task sleeps in looks of 50 ms. A look that returns late by 0.25 s or more is a
stall of that excess, and it writes one line:

    loop stall: 0.40 s, began 2026-10-16T09:30:00Z

The line carries the length and the start time only. No question text, no user
data. A loop busy in short chunks under 0.25 s writes nothing. The switch
`LOOP_STALL_WATCH` (default on; "0", "false", "off" or "no" turns it off) needs
no code deploy. The watcher never raises into the app.
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
                logger.info("loop stall: %.2f s, began %s", late_s, stamp)


def start_loop_stall_watch() -> "asyncio.Task[None] | None":
    """Start the watcher on the running loop, or return None when switched off."""
    if not watch_enabled():
        return None
    return asyncio.get_running_loop().create_task(_watch(), name="loop-stall-watch")


async def stop_loop_stall_watch(task: "asyncio.Task[None] | None") -> None:
    """Cancel the watcher and wait for it. Safe with None."""
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task
