"""Tests for the event loop stall counter (cards 84 and 72, step 3b)."""

import asyncio
import logging
import re
import time

import pytest

from system_03_search_agent.adapters.web_sse import loop_stall

LOGGER = "system_03_search_agent.adapters.web_sse.loop_stall"


def _lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == LOGGER]


async def _run_with_watch(body) -> None:  # type: ignore[no-untyped-def]
    task = loop_stall.start_loop_stall_watch()
    assert task is not None
    await asyncio.sleep(0.12)
    await body()
    await asyncio.sleep(0.12)
    await loop_stall.stop_loop_stall_watch(task)


def test_one_forced_block_logs_one_line(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)

    async def body() -> None:
        time.sleep(0.4)  # noqa: ASYNC251 - the forced block is the test

    asyncio.run(_run_with_watch(body))
    lines = _lines(caplog)
    assert len(lines) == 1
    m = re.fullmatch(r"loop stall: (\d+\.\d\d) s, began \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", lines[0])
    assert m is not None
    assert 0.3 <= float(m.group(1)) <= 0.5


def test_short_blocks_log_nothing(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)

    async def body() -> None:
        for _ in range(10):
            time.sleep(0.1)  # noqa: ASYNC251 - short busy chunk
            await asyncio.sleep(0.01)

    asyncio.run(_run_with_watch(body))
    assert _lines(caplog) == []


def test_cancels_within_one_look() -> None:
    async def go() -> float:
        task = loop_stall.start_loop_stall_watch()
        assert task is not None
        await asyncio.sleep(0.12)
        began = time.monotonic()
        await loop_stall.stop_loop_stall_watch(task)
        assert task.done()
        return time.monotonic() - began

    assert asyncio.run(go()) < 0.05


def test_switch_off_starts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOP_STALL_WATCH", "off")

    async def go() -> None:
        assert loop_stall.start_loop_stall_watch() is None
        await loop_stall.stop_loop_stall_watch(None)

    asyncio.run(go())


def test_lifespan_starts_and_stops_watch(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from system_03_search_agent.adapters.web_sse.app import app

    started: list[object] = []
    real = loop_stall.start_loop_stall_watch

    def spy() -> object:
        task = real()
        started.append(task)
        return task

    monkeypatch.setattr("system_03_search_agent.adapters.web_sse.app.start_loop_stall_watch", spy)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert len(started) == 1
    assert started[0] is not None and started[0].done()  # type: ignore[attr-defined]
