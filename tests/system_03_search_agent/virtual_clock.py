"""A virtual clock for the guardrail's timing tests (R-10's fix round).

An event loop whose `time()` jumps to the next scheduled timer instead of
waiting for it, so a test can run the guardrail on its real 15-second
budget and its real constants in milliseconds, and assert the exact
moments requests were sent.

`run_virtual(monkeypatch, make)` runs the coroutine `make()` on a fresh
virtual loop, with `time.monotonic` in the guardrail's own modules
(`core.graph`, `harness.decide`, `harness.harness`, `harness.jev_client`)
reading the same clock. `time.sleep` there moves the clock forward too,
so a blocking stall of the loop can be staged. Nothing here does real
I/O, which is what lets the selector skip every wait.
"""

from __future__ import annotations

import asyncio
import selectors
import types
from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness import jev_client as jev_client_module


class _Skipping(selectors.DefaultSelector):  # type: ignore[misc, valid-type]
    """A selector that never waits: asked to wait, it moves the loop's clock
    forward by that long instead."""

    def __init__(self, loop: VirtualLoop) -> None:
        super().__init__()
        self._virtual_loop = loop

    def select(self, timeout: float | None = None) -> list[Any]:
        if timeout is None:
            raise RuntimeError("the virtual clock would wait forever: nothing is scheduled")
        if timeout > 0:
            self._virtual_loop.now += timeout
        return []


class VirtualLoop(asyncio.SelectorEventLoop):
    """The loop: `now` is its clock, in seconds."""

    def __init__(self) -> None:
        self.now = 1000.0
        super().__init__(selector=_Skipping(self))

    def time(self) -> float:
        return self.now

    def stall(self, seconds: float) -> None:
        """A blocking stall of the loop: the clock moves, nothing runs."""
        self.now += seconds


def run_virtual(monkeypatch: pytest.MonkeyPatch, make: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
    """Run `make()` on a fresh virtual loop and return its result."""
    loop = VirtualLoop()
    fake_time = types.SimpleNamespace(monotonic=loop.time, sleep=loop.stall, time=lambda: loop.now)
    for module in (graph_module, decide_module, harness_module, jev_client_module):
        monkeypatch.setattr(module, "time", fake_time)
    try:
        return loop.run_until_complete(make())
    finally:
        loop.close()


def now() -> float:
    """The running loop's clock."""
    return asyncio.get_running_loop().time()
