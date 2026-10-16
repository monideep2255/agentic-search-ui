"""Tests for the event loop stall counter (cards 84 and 72, step 3b)."""

import asyncio
import contextlib
import io
import logging
import re
import time
import types

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
    caplog.set_level(logging.WARNING, logger=LOGGER)

    async def body() -> None:
        time.sleep(0.4)  # noqa: ASYNC251 - the forced block is the test

    asyncio.run(_run_with_watch(body))
    lines = _lines(caplog)
    assert len(lines) == 1
    m = re.fullmatch(
        r"event loop lag: (\d+\.\d\d) s \(timers ran late\), began \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",
        lines[0],
    )
    assert m is not None
    assert 0.3 <= float(m.group(1)) <= 0.5


def test_one_task_with_short_blocks_and_real_gaps_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)

    async def body() -> None:
        for _ in range(10):
            time.sleep(0.1)  # noqa: ASYNC251 - short busy chunk
            await asyncio.sleep(0.05)  # a real gap: the watcher's timer runs here

    asyncio.run(_run_with_watch(body))
    assert _lines(caplog) == []


def test_several_busy_tasks_do_produce_a_line(caplog: pytest.LogCaptureFixture) -> None:
    """Pins what the count means: no single block, yet timers ran late."""
    caplog.set_level(logging.WARNING, logger=LOGGER)

    async def worker() -> None:
        for _ in range(10):
            time.sleep(0.1)  # noqa: ASYNC251 - each chunk is short
            await asyncio.sleep(0)

    async def body() -> None:
        await asyncio.gather(*(worker() for _ in range(5)))

    asyncio.run(_run_with_watch(body))
    assert len(_lines(caplog)) >= 1


def test_line_reaches_root_handler_at_warning_on_one_line() -> None:
    """The deployed setup: root at WARNING with its own handler, as alembic leaves it."""
    root = logging.getLogger()
    saved_level, saved_handlers = root.level, root.handlers[:]
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    root.handlers[:] = [handler]
    root.setLevel(logging.WARNING)
    module_logger = logging.getLogger(LOGGER)
    saved_module_level = module_logger.level
    module_logger.setLevel(logging.NOTSET)
    try:

        async def body() -> None:
            time.sleep(0.4)  # noqa: ASYNC251 - the forced block is the test

        asyncio.run(_run_with_watch(body))
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        module_logger.setLevel(saved_module_level)
    out = stream.getvalue().splitlines()
    assert len(out) == 1
    assert out[0].startswith("WARNING event loop lag: ")


def test_measurement_ignores_wall_clock_jumps(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)
    real = time.time
    calls = {"n": 0}

    def jumping() -> float:
        calls["n"] += 1
        return real() + 1000.0 * calls["n"]

    monkeypatch.setattr(loop_stall.time, "time", jumping)

    async def body() -> None:
        await asyncio.sleep(0.2)

    asyncio.run(_run_with_watch(body))
    assert calls["n"] > 0
    assert _lines(caplog) == []


def test_stop_passes_on_a_cancel_aimed_at_the_caller() -> None:
    async def go() -> bool:
        task = loop_stall.start_loop_stall_watch()
        assert task is not None
        await asyncio.sleep(0.06)

        async def caller() -> None:
            await loop_stall.stop_loop_stall_watch(task)

        outer = asyncio.get_running_loop().create_task(caller())
        await asyncio.sleep(0)  # caller reaches `await task`
        outer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await outer
        return outer.cancelled()

    assert asyncio.run(go()) is True


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


def _stub_mcp(monkeypatch: pytest.MonkeyPatch, fail: bool) -> None:
    """Replace the MCP sub-app's lifespan: the real session manager runs once per process."""
    from system_03_search_agent.adapters.web_sse import app as app_module

    @contextlib.asynccontextmanager
    async def fake_lifespan(_app: object):  # type: ignore[no-untyped-def]
        if fail:
            raise RuntimeError("mcp lifespan failed")
        yield

    stub = types.SimpleNamespace(router=types.SimpleNamespace(lifespan_context=fake_lifespan))
    monkeypatch.setattr(app_module, "_mcp_asgi_app", stub)
    monkeypatch.setattr(app_module, "_run_startup_migrations_if_requested", lambda: None)


def _spy_watch(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    from system_03_search_agent.adapters.web_sse import app as app_module

    seen: dict[str, object] = {"started": None, "stopped": 0}
    real_start, real_stop = loop_stall.start_loop_stall_watch, loop_stall.stop_loop_stall_watch

    def start() -> object:
        seen["started"] = real_start()
        return seen["started"]

    async def stop(task: object) -> None:
        seen["stopped"] = int(seen["stopped"]) + 1  # type: ignore[call-overload]
        await real_stop(task)  # type: ignore[arg-type]

    monkeypatch.setattr(app_module, "start_loop_stall_watch", start)
    monkeypatch.setattr(app_module, "stop_loop_stall_watch", stop)
    return seen


def test_lifespan_starts_and_stops_watch(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.adapters.web_sse.app import _lifespan, app

    _stub_mcp(monkeypatch, fail=False)
    seen = _spy_watch(monkeypatch)

    async def go() -> None:
        async with contextlib.asynccontextmanager(_lifespan)(app):
            assert seen["started"] is not None
            assert not seen["started"].done()  # type: ignore[attr-defined]

    asyncio.run(go())
    assert seen["stopped"] == 1
    assert seen["started"].done()  # type: ignore[attr-defined]


def test_lifespan_stops_watch_when_mcp_lifespan_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.adapters.web_sse.app import _lifespan, app

    _stub_mcp(monkeypatch, fail=True)
    seen = _spy_watch(monkeypatch)

    async def go() -> None:
        async with contextlib.asynccontextmanager(_lifespan)(app):
            pass

    with pytest.raises(RuntimeError, match="mcp lifespan failed"):
        asyncio.run(go())
    assert seen["stopped"] == 1
    assert seen["started"].done()  # type: ignore[attr-defined]
