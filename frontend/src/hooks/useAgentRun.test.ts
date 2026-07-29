import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentEvent, DonePayload, ErrorPayload, GuardPayload, TokenPayload } from "../lib/events";
import { consumeEventStream, parseSseFrame, splitSseFrames, useAgentRun } from "./useAgentRun";

/**
 * Builds one SSE frame exactly as `sse_starlette.event.ServerSentEvent`
 * (installed version 3.4.6, this repo's venv) encodes it:
 * `event: <type><sep>data: <json><sep><sep>` with `<sep>` defaulting to
 * `"\r\n"`. See `useAgentRun.ts`'s module docstring for the citation.
 */
function buildFrame(type: string, envelope: unknown): string {
  return `event: ${type}\r\ndata: ${JSON.stringify(envelope)}\r\n\r\n`;
}

function buildEnvelope(type: string, seq: number, payload: unknown) {
  return {
    type,
    version: "v1",
    trace_id: "trace-1",
    seq,
    ts: "2026-07-28T12:00:00Z",
    payload,
  };
}

const GUARD_PASSED: GuardPayload = { passed: true, category: "ok", reason: null };
const TOKEN_A: TokenPayload = { text: "CFTR", marker_ids: [] };
const TOKEN_B: TokenPayload = { text: " is associated", marker_ids: [] };
const DONE: DonePayload = {
  total_cost_usd: 0.01,
  total_tool_calls: 1,
  elapsed_ms: 500,
  trust_outcome: "answer",
};
const NON_FATAL_ERROR: ErrorPayload = {
  fatal: false,
  scope: "tool",
  source: "ncbi_efetch",
  error_class: "transient",
  message: "retrying after a transient timeout",
  retry_after_s: 1,
};
const FATAL_ERROR: ErrorPayload = {
  fatal: true,
  scope: "run",
  source: "agent_loop",
  error_class: "unexpected",
  message: "unrecoverable failure",
  retry_after_s: 0,
};

/** A minimal stand-in for `Response`, matching only what this module reads. */
function makeStreamingResponse(body: ReadableStream<Uint8Array> | null): Response {
  return {
    ok: true,
    status: 200,
    body,
  } as unknown as Response;
}

/** Encodes each string chunk as its own `enqueue` call, so a test can force
 * a frame boundary to fall mid-chunk. */
function makeSseStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(chunks[index]));
      index += 1;
    },
  });
}

describe("splitSseFrames", () => {
  it("splits complete frames from an incomplete trailing remainder", () => {
    const buffer = "event: guard\r\ndata: {}\r\n\r\nevent: think\r\ndata: {}\r\n\r\nevent: pl";
    const { frames, remainder } = splitSseFrames(buffer);
    expect(frames).toHaveLength(2);
    expect(frames[0]).toContain("event: guard");
    expect(frames[1]).toContain("event: think");
    expect(remainder).toBe("event: pl");
  });

  it("normalizes bare \\n the same as \\r\\n", () => {
    const buffer = "event: guard\ndata: {}\n\nevent: think\ndata: {}\n\n";
    const { frames, remainder } = splitSseFrames(buffer);
    expect(frames).toHaveLength(2);
    expect(remainder).toBe("");
  });
});

describe("parseSseFrame", () => {
  it("parses event and data lines", () => {
    const frame = parseSseFrame('event: guard\r\ndata: {"a":1}');
    expect(frame).toEqual({ event: "guard", data: '{"a":1}' });
  });

  it("ignores a comment-only ping frame", () => {
    const frame = parseSseFrame(": ping - 2026-07-28T12:00:00Z");
    expect(frame).toEqual({ event: null, data: null });
  });

  it("joins multiple data: lines with a newline, per the SSE spec", () => {
    const frame = parseSseFrame("event: token\r\ndata: line one\r\ndata: line two");
    expect(frame).toEqual({ event: "token", data: "line one\nline two" });
  });
});

describe("consumeEventStream: ordering and termination", () => {
  it("dispatches events in the exact order the server sent them", async () => {
    const frames =
      buildFrame("guard", buildEnvelope("guard", 0, GUARD_PASSED)) +
      buildFrame("token", buildEnvelope("token", 1, TOKEN_A)) +
      buildFrame("token", buildEnvelope("token", 2, TOKEN_B)) +
      buildFrame("done", buildEnvelope("done", 3, DONE));

    // Split the encoded text across several chunks, deliberately mid-frame,
    // to prove the parser handles a frame arriving across chunk boundaries.
    const midpoint = Math.floor(frames.length / 2);
    const stream = makeSseStream([frames.slice(0, midpoint), frames.slice(midpoint)]);
    const response = makeStreamingResponse(stream);

    const received: AgentEvent[] = [];
    await consumeEventStream(response, (event) => received.push(event));

    expect(received.map((event) => event.type)).toEqual(["guard", "token", "token", "done"]);
    expect((received[1].payload as TokenPayload).text).toBe("CFTR");
    expect((received[2].payload as TokenPayload).text).toBe(" is associated");
  });

  it("stops after a done event, even if more frames are buffered in the same chunk", async () => {
    const frames =
      buildFrame("done", buildEnvelope("done", 0, DONE)) +
      buildFrame("token", buildEnvelope("token", 1, TOKEN_A)); // must never be dispatched
    const stream = makeSseStream([frames]);
    const response = makeStreamingResponse(stream);

    const received: AgentEvent[] = [];
    await consumeEventStream(response, (event) => received.push(event));

    expect(received.map((event) => event.type)).toEqual(["done"]);
  });

  it("does not stop after a non-fatal error, but does stop after a fatal one", async () => {
    const frames =
      buildFrame("guard", buildEnvelope("guard", 0, GUARD_PASSED)) +
      buildFrame("error", buildEnvelope("error", 1, NON_FATAL_ERROR)) +
      buildFrame("token", buildEnvelope("token", 2, TOKEN_A)) +
      buildFrame("error", buildEnvelope("error", 3, FATAL_ERROR)) +
      buildFrame("token", buildEnvelope("token", 4, TOKEN_B)); // must never be dispatched
    const stream = makeSseStream([frames]);
    const response = makeStreamingResponse(stream);

    const received: AgentEvent[] = [];
    await consumeEventStream(response, (event) => received.push(event));

    expect(received.map((event) => event.type)).toEqual(["guard", "error", "token", "error"]);
    const errors = received.filter((event) => event.type === "error");
    expect((errors[0].payload as ErrorPayload).fatal).toBe(false);
    expect((errors[1].payload as ErrorPayload).fatal).toBe(true);
  });

  it("silently discards a comment-only keep-alive ping frame", async () => {
    const frames =
      ": ping - 2026-07-28T12:00:00Z\r\n\r\n" +
      buildFrame("guard", buildEnvelope("guard", 0, GUARD_PASSED)) +
      buildFrame("done", buildEnvelope("done", 1, DONE));
    const stream = makeSseStream([frames]);
    const response = makeStreamingResponse(stream);

    const received: AgentEvent[] = [];
    await consumeEventStream(response, (event) => received.push(event));

    expect(received.map((event) => event.type)).toEqual(["guard", "done"]);
  });
});

describe("useAgentRun", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("dispatches events in arrival order and reaches 'done' status", async () => {
    const frames =
      buildFrame("guard", buildEnvelope("guard", 0, GUARD_PASSED)) +
      buildFrame("token", buildEnvelope("token", 1, TOKEN_A)) +
      buildFrame("done", buildEnvelope("done", 2, DONE));
    fetchMock.mockResolvedValue(makeStreamingResponse(makeSseStream([frames])));

    const { result } = renderHook(() => useAgentRun("run-1", "test-token"));

    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(result.current.events.map((event) => event.type)).toEqual(["guard", "token", "done"]);

    // The real Authorization header this whole ticket exists to send,
    // since the native EventSource API cannot set it (see useAgentRun.ts's
    // docstring).
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("does NOT close on a non-fatal error but DOES close on a fatal one", async () => {
    const frames =
      buildFrame("guard", buildEnvelope("guard", 0, GUARD_PASSED)) +
      buildFrame("error", buildEnvelope("error", 1, NON_FATAL_ERROR)) +
      buildFrame("token", buildEnvelope("token", 2, TOKEN_A)) +
      buildFrame("error", buildEnvelope("error", 3, FATAL_ERROR)) +
      buildFrame("token", buildEnvelope("token", 4, TOKEN_B)); // must never arrive
    fetchMock.mockResolvedValue(makeStreamingResponse(makeSseStream([frames])));

    const { result } = renderHook(() => useAgentRun("run-2", "test-token"));

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.events.map((event) => event.type)).toEqual([
      "guard",
      "error",
      "token",
      "error",
    ]);
    expect(result.current.error).toBe(FATAL_ERROR.message);
  });

  it("aborts the underlying fetch when the component unmounts", async () => {
    // A stream that never closes on its own, so the only way this test's
    // `await` inside consumeEventStream ever resolves is via the abort
    // triggered by unmount.
    let capturedSignal: AbortSignal | undefined;
    fetchMock.mockImplementation((_url: string, init: RequestInit) => {
      capturedSignal = init.signal ?? undefined;
      const stream = new ReadableStream<Uint8Array>({
        start() {
          // Never enqueues, never closes: simulates an open connection.
        },
      });
      return Promise.resolve(makeStreamingResponse(stream));
    });

    const { result, unmount } = renderHook(() => useAgentRun("run-3", "test-token"));

    await waitFor(() => expect(result.current.status).toBe("streaming"));
    expect(capturedSignal?.aborted).toBe(false);

    act(() => {
      unmount();
    });

    expect(capturedSignal?.aborted).toBe(true);
  });

  it("does nothing (status stays 'idle') while runId or token is null", () => {
    const { result } = renderHook(() => useAgentRun(null, null));
    expect(result.current.status).toBe("idle");
    expect(result.current.events).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("re-opens the stream when runId changes, resetting events", async () => {
    const framesForRunA = buildFrame("guard", buildEnvelope("guard", 0, GUARD_PASSED));
    const framesForRunB = buildFrame("done", buildEnvelope("done", 0, DONE));
    fetchMock
      .mockResolvedValueOnce(makeStreamingResponse(makeSseStream([framesForRunA])))
      .mockResolvedValueOnce(makeStreamingResponse(makeSseStream([framesForRunB])));

    const { result, rerender } = renderHook(({ runId }) => useAgentRun(runId, "test-token"), {
      initialProps: { runId: "run-a" },
    });

    await waitFor(() => expect(result.current.events).toHaveLength(1));
    expect(result.current.events[0].type).toBe("guard");

    rerender({ runId: "run-b" });

    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(result.current.events.map((event) => event.type)).toEqual(["done"]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
